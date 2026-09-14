"use client";

/** Katılımcı yönetimi (yalnız eğitmen). API: GET/POST/DELETE /courses/{id}/members */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useId, useState } from "react";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { Member } from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { useSubmit } from "@/lib/use-submit";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { UserIcon } from "@/components/icons";
import { InstructorGate } from "@/components/instructor-gate";
import { ErrorNote, Loading, PageHeader } from "@/components/page-state";
import { Badge, Button, Card, ConfirmAction, EmptyState, Input, Select } from "@/components/ui";

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
  const { user, isInstructor, ready } = useSession(courseId);

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

      <InstructorGate
        ready={ready}
        isInstructor={isInstructor}
        fallback={
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
        }
      >
        <MemberRoster courseId={courseId} currentUserId={user?.id} />
      </InstructorGate>
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
  const [memberQuery, setMemberQuery] = useState("");
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

  const visibleMembers = members?.filter((member) =>
    `${member.full_name ?? ""} ${member.email}`.toLocaleLowerCase("tr-TR").includes(memberQuery.trim().toLocaleLowerCase("tr-TR")),
  );
  return (
    <>
      <AddMemberForm courseId={courseId} onAdded={reload} />

      {error && (
        <ErrorNote
          message={error}
          kind={errorKind}
          requestId={errorRequestId}
          onRetry={reload}
        />
      )}
      {loading && <Loading />}

      {members?.length === 0 && (
        <EmptyState title="Bu derste henüz katılımcı yok. Yukarıdaki alana e-posta yazarak ilk katılımcıyı ekleyin." />
      )}

      {members && members.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
          <div><h2 className="text-xl font-semibold text-fg">Ders katılımcıları</h2><p className="mt-1 text-sm text-fg-muted">{members.length} kayıtlı katılımcı</p></div>
          <Input aria-label="Katılımcılarda ara" placeholder="Ad veya e-posta ile ara" type="search" className="sm:max-w-72" value={memberQuery} onChange={(event) => setMemberQuery(event.target.value)} />
        </div>
      )}
      {visibleMembers?.length === 0 && members && members.length > 0 && (
        <EmptyState title="Aramanızla eşleşen katılımcı bulunamadı." action={<Button variant="secondary" onClick={() => setMemberQuery("")}>Aramayı temizle</Button>} />
      )}
      {visibleMembers && visibleMembers.length > 0 && (
        /*
         * Giriş animasyonu gecikmesizdir ve bu sayfadaki üç yüzeyde aynıdır:
         * form kartı, bu liste ve boş durum kartı aynı işi yapıyor, farklı
         * gecikmeyle açılmaları sırayı anlatmıyordu (DESIGN.md MOTION: çok
         * düşük — hareket yalnız durum değişimini bildirir). Liste ile boş
         * durum aynı yeri paylaştığı için ikisi de `rise`; `EmptyState` bunu
         * kendi içinde sabitlemiş durumda.
         */
        <ul className="rise divide-y divide-border overflow-hidden rounded-[20px] border border-border bg-surface shadow-e1">
          {visibleMembers.map((member) => (
            <li
              key={member.user_id}
              className="flex flex-col items-stretch gap-4 px-5 py-5 transition-colors hover:bg-surface-sunken sm:flex-row sm:items-center sm:justify-between sm:px-6"
            >
              <div className="flex min-w-0 flex-1 items-center gap-3">
                <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-surface-sunken text-fg-muted"><UserIcon size={21} /></span>
                <div className="min-w-0">
                <p className="break-words font-medium text-fg">
                  {member.full_name ?? member.email}
                  {member.user_id === currentUserId && (
                    <span className="ml-2 text-xs text-fg-subtle">(siz)</span>
                  )}
                </p>
                <p className="mt-1 break-words text-sm text-fg-subtle">
                  {member.email}
                </p>
              </div>
              </div>
              <div className="flex flex-wrap items-center gap-3">
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

  const emailId = useId();
  const roleId = useId();
  const hintId = useId();
  const errorId = useId();

  // Buton `aria-disabled` ile beklemeye alınıyor (odağı kaybetmemek için,
  // bkz. ui.tsx `Button`). `aria-disabled` gönderimi kendiliğinden
  // engellemediğinden çift gönderim kapısı `useSubmit`'te duruyor.
  const { busy, error, submit: add } = useSubmit(async () => {
    await api.post(`/courses/${courseId}/members`, { email, role });
    setEmail("");
    onAdded();
  }, "İşlem tamamlanamadı.");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    void add();
  }

  return (
    <Card className="rise mb-7">
      <h2 className="mb-5 text-xl font-semibold text-fg">Katılımcı ekle</h2>
      {/*
       * Etiketler görünür ve `htmlFor` ile bağlı; placeholder yalnız örnek
       * değerdir (DESIGN.md: "Placeholder metni etiket yerine kullanma —
       * odaklanınca kaybolur"). `items-end` etiketli alanlarla butonu aynı
       * taban çizgisine oturtur.
       */}
      <form onSubmit={submit} className="grid items-end gap-4 md:grid-cols-[minmax(0,1fr)_180px_auto]">
        <div className="flex-1">
          <label htmlFor={emailId} className="mb-2 block text-sm font-medium text-fg-muted">
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
          <label htmlFor={roleId} className="mb-2 block text-sm font-medium text-fg-muted">
            Rol
          </label>
          <Select
            id={roleId}
            value={role}
            onChange={(e) => setRole(e.target.value as typeof role)}
          >
            <option value="student">Öğrenci</option>
            <option value="instructor">Eğitmen</option>
          </Select>
        </div>
        <Button type="submit" aria-disabled={busy}>
          {busy ? "Ekleniyor…" : "Derse ekle"}
        </Button>
      </form>
      <p id={hintId} className="mt-4 text-sm text-fg-subtle">
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
