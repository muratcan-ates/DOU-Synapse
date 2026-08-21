"use client";

/** Katılımcı yönetimi (yalnız eğitmen). API: GET/POST/DELETE /courses/{id}/members */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useId, useState } from "react";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { useSession } from "@/lib/session";
import type { Member } from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { ErrorNote, Loading, PageHeader } from "@/components/page-state";
import { Badge, Button, Card, ConfirmAction, EmptyState, Input } from "@/components/ui";

/**
 * Girdi kabuğu — `ui.tsx`'teki `Input` ile birebir aynı ölçüler: 44px yükseklik
 * (DESIGN.md §Responsive dokunma hedefi), 8px köşe, 1px kenarlık, aynı odak
 * halkası. Yükseklik burada 40px'ti; e-posta girdisinin yanında hem yamuk
 * duruyor hem de dokunma hedefinin altında kalıyordu.
 *
 * Bu sabit geçici: `<select>` kabuğu ui.tsx'e `Select` olarak taşınmalı ki sınıf
 * dizisi `Input` ile tek yerde yaşasın (Anayasa XI). Bu görevde ui.tsx başka bir
 * şeride ait olduğu için taşınamadı.
 */
const CONTROL_CLASS =
  "h-11 w-full rounded-lg border border-border-strong bg-surface px-3 text-sm text-fg focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand";

export default function MembersPage() {
  return (
    <AppShell>
      <MembersView />
    </AppShell>
  );
}

function MembersView() {
  const { courseId } = useParams<{ courseId: string }>();
  /*
   * Rol kapısı yalnız ARAYÜZÜ şekillendirir; güvenlik kontrolü DEĞİLDİR.
   * Yetki her zaman sunucuda doğrulanır (Anayasa II): bu ekranın beslendiği üç
   * uç da `require_course_instructor`'dan geçer, yani öğrenci isteği burada
   * hiçbir şey olmasa bile 403 döner. Kapı kaldırılırsa açık oluşmaz — sadece
   * öğrenci çalışmayan bir form görür (Anayasa XI: etkin görünüp iş yapmayan
   * yüzey kusurdur). Bu yüzden buradaki kontrolü "gereksiz" diye silmeyin,
   * ama sunucudaki kontrolün yerine de saymayın.
   *
   * `ready` gelmeden hiçbir dala girilmez (Anayasa IV, fail-closed): rol
   * localStorage'dan ilk efektte okunur, o ana kadar "eğitmen değil" varsayımı
   * eğitmene bir kare boyunca yanlış ekran gösterirdi.
   */
  const { user, isInstructor, ready } = useSession();

  return (
    <div>
      <CourseNav courseId={courseId} />

      <PageHeader
        title="Katılımcılar"
        description={
          isInstructor
            ? "Öğrenciler yalnızca kayıtlı oldukları dersin materyalini görür; asistan da yalnız o materyalden cevap verir."
            : undefined
        }
      />

      {!ready ? (
        <Loading />
      ) : isInstructor ? (
        <MemberRoster courseId={courseId} currentUserId={user?.id} />
      ) : (
        /*
         * Sekme öğrenciye gösterilmiyor (course-nav.tsx `instructorOnly`) ama
         * adres çubuğuna yazılarak girilebiliyor. Burada kırmızı/uyarı yok:
         * yetkisi olmayan sayfaya girmek bir arıza değil, sakin bir yönlendirme
         * konusudur (DESIGN.md: hata dışı durumlar hata gibi gösterilmez).
         */
        <EmptyState
          title="Katılımcı listesi yalnızca dersin eğitmenine gösterilir."
          action={
            <Link
              href={`/courses/${courseId}`}
              className="text-sm text-brand hover:text-brand-strong"
            >
              Ders sayfasına dön
            </Link>
          }
        />
      )}
    </div>
  );
}

/**
 * Liste ve ekleme formu — yalnız eğitmen dalında mount edilir.
 *
 * Ayrı bileşen olmasının sebebi kozmetik değil: `useResource` mount olur olmaz
 * istek atar. Kapı aynı bileşenin içinde olsaydı öğrenci de GET atar ve ekrana
 * 403 metni düşerdi; kapı bu yüzden isteği hiç başlatmayacak şekilde kurulmuş.
 */
function MemberRoster({
  courseId,
  currentUserId,
}: {
  courseId: string;
  currentUserId?: string;
}) {
  const fetchMembers = useCallback(
    () => api.get<Member[]>(`/courses/${courseId}/members`),
    [courseId],
  );
  const {
    data: members,
    error,
    errorKind,
    errorRequestId,
    loading,
    reload,
  } = useResource(fetchMembers, [courseId]);

  return (
    <>
      <AddMemberForm courseId={courseId} onAdded={reload} />

      {error && (
        <ErrorNote message={error} kind={errorKind} requestId={errorRequestId} />
      )}
      {loading && <Loading />}

      {members?.length === 0 && (
        <EmptyState title="Bu derste henüz katılımcı yok. Yukarıdaki alana e-posta yazarak ilk katılımcıyı ekleyin." />
      )}

      {members && members.length > 0 && (
        /*
         * Giriş animasyonu gecikmesizdir ve bu sayfadaki üç yüzeyde aynıdır:
         * form kartı, bu liste ve boş durum kartı aynı işi yapıyor, farklı
         * gecikmeyle açılmaları sırayı anlatmıyordu (DESIGN.md MOTION: çok
         * düşük — hareket yalnız durum değişimini bildirir). Liste ile boş
         * durum aynı yeri paylaştığı için ikisi de `rise`; `EmptyState` bunu
         * kendi içinde sabitlemiş durumda.
         */
        <ul className="rise divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface">
          {members.map((member) => (
            <li
              key={member.user_id}
              className="flex flex-wrap items-center justify-between gap-3 px-6 py-4"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-fg">
                  {member.full_name ?? member.email}
                  {member.user_id === currentUserId && (
                    <span className="ml-2 text-xs text-fg-subtle">(siz)</span>
                  )}
                </p>
                <p className="mt-0.5 font-mono text-xs text-fg-subtle">
                  {member.email}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <Badge tone={member.role === "instructor" ? "info" : "neutral"}>
                  {member.role === "instructor" ? "Eğitmen" : "Öğrenci"}
                </Badge>
                {member.status === "revoked" ? (
                  <Badge tone="warning">Erişim kapalı</Badge>
                ) : (
                  // Kendini çıkarma yok: dersin son eğitmeni kendini atarsa
                  // ders sahipsiz kalır.
                  member.user_id !== currentUserId && (
                    <ConfirmAction
                      label="Çıkar"
                      confirmLabel="Evet, çıkar"
                      busyLabel="Çıkarılıyor…"
                      question="Erişimi kapatılacak."
                      ariaLabel={`${member.email} kullanıcısını dersten çıkar`}
                      onConfirm={async () => {
                        await api.delete(
                          `/courses/${courseId}/members/${member.user_id}`,
                        );
                        await reload();
                      }}
                    />
                  )
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function AddMemberForm({
  courseId,
  onAdded,
}: {
  courseId: string;
  onAdded: () => void;
}) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"student" | "instructor">("student");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const emailId = useId();
  const roleId = useId();
  const hintId = useId();
  const errorId = useId();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    // Buton `aria-disabled` ile beklemeye alınıyor (odağı kaybetmemek için,
    // bkz. ui.tsx `Button`). `aria-disabled` gönderimi kendiliğinden
    // engellemediğinden çift gönderim kapısı burada duruyor.
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.post(`/courses/${courseId}/members`, { email, role });
      setEmail("");
      onAdded();
    } catch (err) {
      setError(errorMessage(err, "İşlem tamamlanamadı."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="rise mb-6">
      {/*
       * Etiketler görünür ve `htmlFor` ile bağlı; placeholder yalnız örnek
       * değerdir (DESIGN.md: "Placeholder metni etiket yerine kullanma —
       * odaklanınca kaybolur"). `items-end` etiketli alanlarla butonu aynı
       * taban çizgisine oturtur.
       */}
      <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label htmlFor={emailId} className="mb-1 block text-xs text-fg-muted">
            Katılımcı e-postası
          </label>
          <Input
            id={emailId}
            type="email"
            placeholder="ogrenci@dogus.edu.tr"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            /* Yardım metni her zaman, hata metni yalnız varken bağlı: ekran
               okuyucu alana girince ikisini de duyar. */
            aria-describedby={error ? `${hintId} ${errorId}` : hintId}
            aria-invalid={error ? true : undefined}
            required
          />
        </div>
        <div>
          <label htmlFor={roleId} className="mb-1 block text-xs text-fg-muted">
            Rol
          </label>
          <select
            id={roleId}
            value={role}
            onChange={(e) => setRole(e.target.value as typeof role)}
            className={CONTROL_CLASS}
          >
            <option value="student">Öğrenci</option>
            <option value="instructor">Eğitmen</option>
          </select>
        </div>
        <Button type="submit" aria-disabled={busy}>
          {busy ? "Ekleniyor…" : "Derse ekle"}
        </Button>
      </form>
      <p id={hintId} className="mt-2 text-xs text-fg-subtle">
        Kullanıcının sisteme daha önce giriş yapmış olması gerekir.
      </p>
      {error && (
        <div id={errorId} className="mt-2">
          <ErrorNote message={error} />
        </div>
      )}
    </Card>
  );
}
