"""Sınav blueprint uçları — 002 US3 (T504).

Router `main.py`'ye lider turunda ZATEN kaydedildi; bu dosya yalnız gövde ekler ve
`main.py`'ye hiç dokunmaz. Yol öneki `/courses/{course_id}` ve yetkilendirme
`CourseInstructorDep`: blueprint öğretmenin aracıdır, öğrenci taslak bir sınavı
görmez (FR-111).

**Öğrenci ayağı burada değil.** Yayınlanmış bir sınava girmek `exams.py`'nin işidir
(oturum orada açılır, süre kuralları orada yaşar). Bu dosya sınavı KURAR, o dosya
sınavı VERDİRİR. İkisini aynı router'a koymak, öğrenci yüzeyini eğitmen
bağımlılığının altına sokardı.

Hücre kümesi hep BÜTÜN olarak yazılır (sil + yaz). Tek hücrelik güncelleme ne
politika ne yetki olarak vardır: FR-112 doğrulaması küme üzerinde yapılır ve tekil
bir güncelleme doğrulamayı atlayıp tutarsız bir dağılım bırakabilirdi.

**Güncelleme ve kalem yazma neden PATCH/PUT değil POST.** İkisi de bu yolların
doğal fiili olurdu, ama `apps/web/lib/api.ts` yalnız get/post/upload/delete
taşıyor ve o dosya bu şeritte DEĞİŞTİRİLMEYECEK dosyalar arasında (frontend
reliability şeridinin T401-T403'ü orada yaşıyor). İki fiil eklemek için ortak bir
dosyaya dokunmak, REST saflığından daha pahalıydı. Yol sayısı değişmedi; yalnız
aynı yolların fiili farklı.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CourseContext, CourseInstructorDep, SessionDep
from app.core.db import db_now
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.assessment import (
    BlueprintCell,
    ExamBlueprint,
    ExamItem,
    ExamVersion,
    ExamVersionStatus,
    LearningOutcome,
    Question,
    QuestionDifficulty,
    QuestionStatus,
    QuestionType,
    Topic,
)
from app.modules.assessment.blueprint import (
    cell_label,
    outcome_codes_of,
    published_version_of,
    readiness_report,
    snapshot_of,
    supersede_published,
    validate_distribution,
)
from app.schemas.blueprint import (
    BlueprintCellIn,
    BlueprintCellOut,
    BlueprintCreate,
    BlueprintOut,
    BlueprintUpdate,
    DistributionTargets,
    ExamItemIn,
    ExamItemOut,
    ExamVersionOut,
    LearningOutcomeCreate,
    LearningOutcomeOut,
    PublishOut,
    ReadinessOut,
    TopicShare,
)

router = APIRouter(prefix="/courses/{course_id}", tags=["blueprints"])


# ---------------------------------------------------------------------------
# Yükleme yardımcıları
# ---------------------------------------------------------------------------


async def _load_blueprint(
    session: AsyncSession, blueprint_id: UUID, context: CourseContext
) -> ExamBlueprint:
    """Blueprint'i yükler. Başka dersin blueprint'i, varlığı sızdırılmadan 404 döner."""
    blueprint = await session.get(ExamBlueprint, blueprint_id)
    if blueprint is None or blueprint.course_id != context.course_id:
        raise NotFoundError("Sınav blueprint'i bulunamadı.")
    return blueprint


async def _load_version(
    session: AsyncSession, version_id: UUID, blueprint: ExamBlueprint
) -> ExamVersion:
    version = await session.get(ExamVersion, version_id)
    if version is None or version.blueprint_id != blueprint.id:
        raise NotFoundError("Sınav sürümü bulunamadı.")
    return version


async def _cells_of(session: AsyncSession, blueprint_id: UUID) -> list[BlueprintCell]:
    rows = await session.execute(
        select(BlueprintCell).where(BlueprintCell.blueprint_id == blueprint_id)
    )
    return list(rows.scalars().all())


async def _blueprint_out(session: AsyncSession, blueprint: ExamBlueprint) -> BlueprintOut:
    """Zarfı kurar; toplamlar ve konu dağılımı TÜRETİLİR, saklanmaz."""
    cells = await _cells_of(session, blueprint.id)
    codes = await outcome_codes_of(session, [cell.learning_outcome_id for cell in cells])

    published = await published_version_of(session, blueprint.id)

    return BlueprintOut(
        id=blueprint.id,
        course_id=blueprint.course_id,
        title=blueprint.title,
        description=blueprint.description,
        duration_minutes=blueprint.duration_minutes,
        max_attempts=blueprint.max_attempts,
        opens_at=blueprint.opens_at,
        closes_at=blueprint.closes_at,
        created_at=blueprint.created_at,
        updated_at=blueprint.updated_at,
        cells=[
            BlueprintCellOut(
                id=cell.id,
                learning_outcome_id=cell.learning_outcome_id,
                difficulty=cell.difficulty,
                question_type=cell.question_type,
                question_count=cell.question_count,
                points_per_question=cell.points_per_question,
                label=cell_label(
                    codes.get(cell.learning_outcome_id, "?"), cell.difficulty, cell.question_type
                ),
            )
            for cell in cells
        ],
        total_questions=sum(cell.question_count for cell in cells),
        total_points=sum(cell.question_count * cell.points_per_question for cell in cells),
        topic_distribution=await _topic_distribution(session, cells),
        published_version_no=published.version_no if published else None,
    )


async def _topic_distribution(
    session: AsyncSession, cells: list[BlueprintCell]
) -> list[TopicShare]:
    """Konu dağılımı — `learning_outcomes.topic_id` üzerinden TÜRETİLİR.

    Ayrı bir hücre ekseni değildir (data-model.md §8 madde 2). Konusuz çıktıdan
    gelen sorular `topic_id=None` satırında toplanır ve ekranda öyle gösterilir;
    sessizce yuvarlanmaz (Anayasa III).
    """
    if not cells:
        return []

    rows = await session.execute(
        select(LearningOutcome.id, Topic.id, Topic.name)
        .select_from(LearningOutcome)
        .outerjoin(Topic, Topic.id == LearningOutcome.topic_id)
        .where(LearningOutcome.id.in_({cell.learning_outcome_id for cell in cells}))
    )
    topic_of = {row[0]: (row[1], row[2]) for row in rows}

    totals: dict[tuple[UUID | None, str | None], int] = {}
    for cell in cells:
        key = topic_of.get(cell.learning_outcome_id, (None, None))
        totals[key] = totals.get(key, 0) + cell.question_count

    return [
        TopicShare(topic_id=topic_id, topic_name=name, question_count=count)
        for (topic_id, name), count in sorted(
            totals.items(), key=lambda item: (item[0][1] is None, item[0][1] or "")
        )
    ]


async def _write_cells(
    session: AsyncSession,
    blueprint: ExamBlueprint,
    cells: list[BlueprintCellIn],
    targets: DistributionTargets | None,
) -> None:
    """Hücre kümesini doğrular ve BÜTÜN olarak yazar (sil + yaz).

    Doğrulama yazmadan ÖNCE koşar (FR-112): tutarsız dağılım kaydedilmez ve hangi
    hücrenin tutmadığı söylenir.
    """
    codes = await outcome_codes_of(session, [cell.learning_outcome_id for cell in cells])
    # Başka dersin çıktısı iliştirilemesin: kod sözlüğü yalnız bu dersin
    # çıktılarından kurulmalı (RLS zaten kapatıyor, uygulama da bağımsız kapatır).
    course_outcomes = {
        row[0]
        for row in await session.execute(
            select(LearningOutcome.id).where(LearningOutcome.course_id == blueprint.course_id)
        )
    }
    codes = {oid: code for oid, code in codes.items() if oid in course_outcomes}

    problems = validate_distribution(cells, outcome_codes=codes, targets=targets)
    if problems:
        raise ValidationError(" ".join(problems))

    await session.execute(delete(BlueprintCell).where(BlueprintCell.blueprint_id == blueprint.id))
    for cell in cells:
        session.add(
            BlueprintCell(
                course_id=blueprint.course_id,
                blueprint_id=blueprint.id,
                learning_outcome_id=cell.learning_outcome_id,
                difficulty=cell.difficulty,
                question_type=cell.question_type,
                question_count=cell.question_count,
                points_per_question=cell.points_per_question,
            )
        )
    await session.flush()


# ---------------------------------------------------------------------------
# Öğrenme çıktıları (FR-110)
# ---------------------------------------------------------------------------


@router.post(
    "/learning-outcomes",
    response_model=LearningOutcomeOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_learning_outcome(
    payload: LearningOutcomeCreate, context: CourseInstructorDep, session: SessionDep
) -> LearningOutcome:
    """Ders bazlı ölçülebilir kazanım tanımlar.

    Kod derste büyük/küçük harf duyarsız tekildir; ikinci kez aynı kod 409 döner.
    """
    if payload.topic_id is not None:
        topic = await session.get(Topic, payload.topic_id)
        if topic is None or topic.course_id != context.course_id:
            raise NotFoundError("Konu bulunamadı.")

    outcome = LearningOutcome(
        course_id=context.course_id,
        code=payload.code.strip(),
        description=payload.description.strip(),
        topic_id=payload.topic_id,
        created_by=context.user_id,
    )
    session.add(outcome)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError(
            f"Bu derste '{payload.code.strip()}' kodlu bir öğrenme çıktısı zaten var."
        ) from exc
    return outcome


@router.get("/learning-outcomes", response_model=list[LearningOutcomeOut])
async def list_learning_outcomes(
    context: CourseInstructorDep, session: SessionDep
) -> list[LearningOutcome]:
    rows = await session.execute(
        select(LearningOutcome)
        .where(LearningOutcome.course_id == context.course_id)
        .order_by(LearningOutcome.code)
    )
    return list(rows.scalars().all())


# ---------------------------------------------------------------------------
# Blueprint (FR-111, FR-112)
# ---------------------------------------------------------------------------


@router.post("/blueprints", response_model=BlueprintOut, status_code=status.HTTP_201_CREATED)
async def create_blueprint(
    payload: BlueprintCreate, context: CourseInstructorDep, session: SessionDep
) -> BlueprintOut:
    """Blueprint'i hücreleriyle birlikte kurar.

    Sorulardan ÖNCE var olur: çatı önce çizilir, kâğıt sonra doldurulur.
    """
    blueprint = ExamBlueprint(
        course_id=context.course_id,
        title=payload.title.strip(),
        description=payload.description,
        duration_minutes=payload.duration_minutes,
        max_attempts=payload.max_attempts,
        opens_at=payload.opens_at,
        closes_at=payload.closes_at,
        created_by=context.user_id,
    )
    session.add(blueprint)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ValidationError(
            "Yayın penceresi geçersiz: açılış tarihi kapanıştan önce olmalı."
        ) from exc

    await _write_cells(session, blueprint, payload.cells, payload.targets)
    return await _blueprint_out(session, blueprint)


@router.get("/blueprints", response_model=list[BlueprintOut])
async def list_blueprints(context: CourseInstructorDep, session: SessionDep) -> list[BlueprintOut]:
    rows = await session.execute(
        select(ExamBlueprint)
        .where(ExamBlueprint.course_id == context.course_id)
        .order_by(ExamBlueprint.created_at.desc(), ExamBlueprint.id.desc())
    )
    return [await _blueprint_out(session, blueprint) for blueprint in rows.scalars().all()]


@router.get("/blueprints/{blueprint_id}", response_model=BlueprintOut)
async def get_blueprint(
    blueprint_id: UUID, context: CourseInstructorDep, session: SessionDep
) -> BlueprintOut:
    blueprint = await _load_blueprint(session, blueprint_id, context)
    return await _blueprint_out(session, blueprint)


@router.post("/blueprints/{blueprint_id}", response_model=BlueprintOut)
async def update_blueprint(
    blueprint_id: UUID,
    payload: BlueprintUpdate,
    context: CourseInstructorDep,
    session: SessionDep,
) -> BlueprintOut:
    """Blueprint meta verisini ve gerekirse hücre kümesini günceller.

    Yayınlanmış bir sürüm varken hücreleri düzenlemek SERBESTTİR: yayınlanmış
    sürümün dağılım kanıtı kendi `blueprint_snapshot`'ında dondurulmuştur ve bu
    düzenlemeden etkilenmez (data-model.md §8 madde 1). Kilitleme yolu seçilseydi,
    v1 yayındayken dağılımı düzeltmek isteyen öğretmenin önce sınavı yayından
    kaldırması gerekirdi.
    """
    blueprint = await _load_blueprint(session, blueprint_id, context)

    for field in ("title", "description", "duration_minutes", "max_attempts"):
        value = getattr(payload, field)
        if value is not None:
            setattr(blueprint, field, value.strip() if isinstance(value, str) else value)
    # Pencere alanları None ile TEMİZLENEBİLMELİ, bu yüzden ayrı ele alınıyor:
    # "gönderilmedi" ile "sınırı kaldır" aynı şey değil.
    fields_set = payload.model_fields_set
    if "opens_at" in fields_set:
        blueprint.opens_at = payload.opens_at
    if "closes_at" in fields_set:
        blueprint.closes_at = payload.closes_at

    blueprint.updated_at = await db_now(session)

    if payload.cells is not None:
        await _write_cells(session, blueprint, payload.cells, payload.targets)

    try:
        await session.flush()
    except IntegrityError as exc:
        raise ValidationError(
            "Yayın penceresi geçersiz: açılış tarihi kapanıştan önce olmalı."
        ) from exc

    return await _blueprint_out(session, blueprint)


@router.delete("/blueprints/{blueprint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_blueprint(
    blueprint_id: UUID, context: CourseInstructorDep, session: SessionDep
) -> None:
    """Blueprint'i siler.

    Yayınlanmış bir sürüme bağlı oturum varsa veritabanı RESTRICT ile reddeder ve
    bu 409'a çevrilir: kanıtı olan bir sınav silinemez.
    """
    blueprint = await _load_blueprint(session, blueprint_id, context)
    await session.delete(blueprint)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "Bu sınavın yürüyen ya da tamamlanmış oturumları var; silinemez. "
            "Yayından kaldırmak için sürümü değiştirin."
        ) from exc


# ---------------------------------------------------------------------------
# Sürümler (FR-114, FR-115)
# ---------------------------------------------------------------------------


async def _version_out(session: AsyncSession, version: ExamVersion) -> ExamVersionOut:
    totals = (
        await session.execute(
            select(func.count(ExamItem.id), func.coalesce(func.sum(ExamItem.points), 0)).where(
                ExamItem.exam_version_id == version.id
            )
        )
    ).one()
    return ExamVersionOut(
        id=version.id,
        blueprint_id=version.blueprint_id,
        version_no=version.version_no,
        status=version.status,
        published_at=version.published_at,
        superseded_at=version.superseded_at,
        created_at=version.created_at,
        item_count=int(totals[0]),
        total_points=int(totals[1]),
    )


@router.post(
    "/blueprints/{blueprint_id}/versions",
    response_model=ExamVersionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    blueprint_id: UUID, context: CourseInstructorDep, session: SessionDep
) -> ExamVersionOut:
    """Yeni bir TASLAK sürüm açar. Numara mevcut en büyüğün bir fazlasıdır.

    Sürüm boş doğar; kalemler ayrı bir çağrıyla yazılır. Böylece "sürüm oluştur" ve
    "kâğıdı doldur" ayrı ayrı geri alınabilir işlemler olur.
    """
    blueprint = await _load_blueprint(session, blueprint_id, context)

    highest = await session.scalar(
        select(func.max(ExamVersion.version_no)).where(ExamVersion.blueprint_id == blueprint.id)
    )
    version = ExamVersion(
        course_id=blueprint.course_id,
        blueprint_id=blueprint.id,
        version_no=(highest or 0) + 1,
        status=ExamVersionStatus.DRAFT,
    )
    session.add(version)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "Bu sınav için aynı anda başka bir sürüm oluşturuldu; sayfayı yenileyip tekrar deneyin."
        ) from exc
    return await _version_out(session, version)


@router.get("/blueprints/{blueprint_id}/versions", response_model=list[ExamVersionOut])
async def list_versions(
    blueprint_id: UUID, context: CourseInstructorDep, session: SessionDep
) -> list[ExamVersionOut]:
    blueprint = await _load_blueprint(session, blueprint_id, context)
    rows = await session.execute(
        select(ExamVersion)
        .where(ExamVersion.blueprint_id == blueprint.id)
        .order_by(ExamVersion.version_no.desc())
    )
    return [await _version_out(session, version) for version in rows.scalars().all()]


@router.post(
    "/blueprints/{blueprint_id}/versions/{version_id}/items",
    response_model=list[ExamItemOut],
)
async def set_version_items(
    blueprint_id: UUID,
    version_id: UUID,
    payload: list[ExamItemIn],
    context: CourseInstructorDep,
    session: SessionDep,
) -> list[ExamItemOut]:
    """Kâğıdı bütün olarak yazar. YALNIZ taslak sürümde çalışır.

    Yayınlanmış sürümde kalem yazmak yalnız burada değil, RLS politikasında ve
    yetki düzeyinde de kapalıdır (`exam_items`'a UPDATE yetkisi yok, INSERT/DELETE
    politikaları `status='draft'` istiyor). Üç katman da bağımsız olarak doğru
    davranmalı (Anayasa II).

    `points` blueprint hücresinden **yayın anında değil, kalem yazılırken**
    kopyalanır: puanı kâğıtla birlikte görmek, yayın kapısına gelmeden önce
    toplamın tutup tutmadığını gösterir.
    """
    blueprint = await _load_blueprint(session, blueprint_id, context)
    version = await _load_version(session, version_id, blueprint)

    if version.status is not ExamVersionStatus.DRAFT:
        raise ConflictError(
            "Yayınlanmış bir sınavın soru listesi değiştirilemez. Değişiklik için yeni "
            "bir sürüm oluşturun; yürüyen oturumlar başladıkları sürümü görmeye devam eder."
        )

    question_ids = [item.question_id for item in payload]
    if len(set(question_ids)) != len(question_ids):
        raise ValidationError("Aynı soru kâğıda iki kez konulamaz.")

    questions = {
        question.id: question
        for question in (
            await session.execute(select(Question).where(Question.id.in_(question_ids)))
        ).scalars()
    }
    for question_id in question_ids:
        question = questions.get(question_id)
        if question is None or question.course_id != blueprint.course_id:
            raise NotFoundError("Soru bu derste bulunamadı.")
        if question.status is not QuestionStatus.APPROVED:
            # FR-119: onaysız soru öğrenciye ulaşamaz. Kapı burada da kapalı.
            raise ConflictError(
                "Onaylanmamış bir soru sınava konulamaz. Önce soruyu havuzda onaylayın."
            )

    cells = await _cells_of(session, blueprint.id)
    points_of: dict[tuple[UUID, QuestionDifficulty, QuestionType], int] = {
        (cell.learning_outcome_id, cell.difficulty, cell.question_type): cell.points_per_question
        for cell in cells
    }

    await session.execute(delete(ExamItem).where(ExamItem.exam_version_id == version.id))
    for index, item in enumerate(payload, start=1):
        question = questions[item.question_id]
        # Sınıflandırılmamış sorunun hücresi yoktur ve 1 puanla girer; yayın kapısı
        # onu zaten ayrı bir madde olarak reddedecek (data-model.md §8 madde 7).
        points = 1
        if question.learning_outcome_id is not None and question.difficulty is not None:
            points = points_of.get(
                (question.learning_outcome_id, question.difficulty, question.type), 1
            )
        session.add(
            ExamItem(
                course_id=blueprint.course_id,
                exam_version_id=version.id,
                position=item.position or index,
                question_id=item.question_id,
                points=points,
            )
        )
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ValidationError("Kâğıtta aynı sıra numarası iki kez kullanılmış.") from exc

    return await _items_out(session, version)


async def _items_out(session: AsyncSession, version: ExamVersion) -> list[ExamItemOut]:
    rows = await session.execute(
        select(ExamItem, Question)
        .join(Question, Question.id == ExamItem.question_id)
        .where(ExamItem.exam_version_id == version.id)
        .order_by(ExamItem.position)
    )
    return [
        ExamItemOut(
            id=item.id,
            position=item.position,
            question_id=item.question_id,
            points=item.points,
            question_type=question.type,
            difficulty=question.difficulty,
            learning_outcome_id=question.learning_outcome_id,
            stem=str(question.payload.get("stem") or question.payload.get("prompt") or ""),
        )
        for item, question in rows
    ]


@router.get(
    "/blueprints/{blueprint_id}/versions/{version_id}/items",
    response_model=list[ExamItemOut],
)
async def list_version_items(
    blueprint_id: UUID, version_id: UUID, context: CourseInstructorDep, session: SessionDep
) -> list[ExamItemOut]:
    blueprint = await _load_blueprint(session, blueprint_id, context)
    version = await _load_version(session, version_id, blueprint)
    return await _items_out(session, version)


@router.get(
    "/blueprints/{blueprint_id}/versions/{version_id}/readiness",
    response_model=ReadinessOut,
)
async def get_readiness(
    blueprint_id: UUID, version_id: UUID, context: CourseInstructorDep, session: SessionDep
) -> ReadinessOut:
    """FR-114'ün raporu: yayınlamadan önce neyin tutmadığını gösterir.

    Yayın ucu aynı raporu kullanır; ayrı bir uç olmasının sebebi öğretmenin kapıya
    çarpmadan önce eksiği görebilmesidir.
    """
    blueprint = await _load_blueprint(session, blueprint_id, context)
    version = await _load_version(session, version_id, blueprint)
    return await readiness_report(session, version)


@router.post("/blueprints/{blueprint_id}/versions/{version_id}/publish", response_model=PublishOut)
async def publish_version(
    blueprint_id: UUID, version_id: UUID, context: CourseInstructorDep, session: SessionDep
) -> PublishOut:
    """Sürümü yayınlar: kapıyı koşturur, dağılımı dondurur, öncekini superseded yapar.

    Sıra önemli — önceki sürüm `superseded` yapılmadan yenisi yayınlanamaz:
    `exam_versions_one_published` kısmi tekil indeksi aynı anda iki yayınlanmış
    sürüme izin vermez ve bu kural yapısaldır, uygulama koduna sorulmaz.

    Yürüyen oturumlar ETKİLENMEZ: eski sürümün satırı ve kalemleri yerinde durur,
    `exam_versions_read`'in üçüncü dalı oturum sahibine okumayı sürdürür.
    """
    blueprint = await _load_blueprint(session, blueprint_id, context)
    version = await _load_version(session, version_id, blueprint)

    if version.status is ExamVersionStatus.PUBLISHED:
        raise ConflictError("Bu sürüm zaten yayında.")
    if version.status is ExamVersionStatus.SUPERSEDED:
        raise ConflictError(
            "Yerine yenisi yayınlanmış bir sürüm tekrar yayınlanamaz. Yeni bir sürüm oluşturun."
        )

    report = await readiness_report(session, version)
    if not report.ready:
        detay = " ".join(
            [cell.label for cell in report.missing_cells]
            + [item.label for item in report.unclassified_items]
        )
        raise ConflictError(f"{report.message} {detay}")

    cells = await _cells_of(session, blueprint.id)
    codes = await outcome_codes_of(session, [cell.learning_outcome_id for cell in cells])

    now = await db_now(session)
    await supersede_published(session, blueprint.id, now=now)

    version.status = ExamVersionStatus.PUBLISHED
    version.published_at = now
    version.published_by = context.user_id
    version.blueprint_snapshot = snapshot_of(cells, codes)
    await session.flush()

    return PublishOut(
        version=await _version_out(session, version),
        blueprint_snapshot=version.blueprint_snapshot or [],
        message=(
            f"{version.version_no}. sürüm yayınlandı. Yayın anındaki dağılım donduruldu; "
            "blueprint sonradan düzenlense de bu sürümün kanıtı değişmez."
        ),
    )
