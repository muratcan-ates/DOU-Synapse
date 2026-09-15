"use client";

/** Ders listesi + ders açma (eğitmen). */

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import type { Course } from "@/lib/types";
import { usePagedResource } from "@/lib/use-paged-resource";
import { useSubmit } from "@/lib/use-submit";
import { AppShell } from "@/components/app-shell";
import { ChevronRightIcon } from "@/components/icons";
import { CourseCover } from "@/components/course-cover";
import { Field } from "@/components/field";
import { ErrorNote, Loading, LoadMore } from "@/components/page-state";
import { Badge, Button, Card, EmptyState, Input } from "@/components/ui";

export default function CoursesPage() {
  return (
    <AppShell>
      <CourseList />
    </AppShell>
  );
}

function CourseList() {
  const [creating, setCreating] = useState(false);
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<"all" | "instructor" | "student">("all");
  const searchId = useId();
  const formId = useId();
  const toggleRef = useRef<HTMLButtonElement>(null);
  const opened = useRef(false);

  const {
    data: courses,
    error,
    refreshError,
    errorKind,
    errorRequestId,
    loading,
    loadingMore,
    loadMore,
    nextCursor,
    pageError,
    reload,
  } = usePagedResource<Course>("/courses", []);

  /*
   * Form kapanırken odak tetikleyiciye geri döner. Form DOM'dan kalktığında
   * (vazgeçildiğinde ya da ders oluşturulduğunda) odak kendiliğinden
   * `<body>`'ye düşer ve klavyeyle çalışan kullanıcı sayfanın en başına atılır.
   * Açılış yönünde bir şey yapılmaz: odağı ilk alana `CreateCourseForm` kendi
   * mount'unda taşır. İlk render'da hiçbir şey olmamalı — bileşen sayfayla
   * birlikte mount olurken odak çalınmaz; `opened` bunun için var.
   */
  useEffect(() => {
    if (creating) {
      opened.current = true;
    } else if (opened.current) {
      opened.current = false;
      toggleRef.current?.focus();
    }
  }, [creating]);

  // Ekranı kapatan hata: tek çıkış tarayıcıyı yenilemek olmamalı.
  if (error)
    return (
      <ErrorNote
        message={error}
        kind={errorKind}
        requestId={errorRequestId}
        onRetry={reload}
      />
    );
  if (loading || !courses) return <Loading />;

  const normalizedQuery = query.trim().toLocaleLowerCase("tr-TR");
  const filteredCourses = courses.filter((course) =>
    (roleFilter === "all" || course.role === roleFilter) &&
    `${course.code} ${course.title}`.toLocaleLowerCase("tr-TR").includes(normalizedQuery),
  );

  return (
    <div>
      <header className="mb-8 flex flex-wrap items-end justify-between gap-5 lg:mb-10">
        <div className="min-w-0">
          <h1 className="text-[2rem] font-semibold leading-tight tracking-[-0.035em] text-fg sm:text-[2.25rem]">Derslerim</h1>
          <p className="mt-3 max-w-xl text-base leading-relaxed text-fg-muted">Dersinizi seçin; kaynaklara, asistana ve sınavlara ulaşın.</p>
        </div>
        <Button
          ref={toggleRef}
          variant={creating ? "secondary" : "primary"}
          aria-expanded={creating}
          aria-controls={creating ? formId : undefined}
          onClick={() => setCreating((v) => !v)}
        >
          {!creating && <span aria-hidden="true" className="text-xl font-normal leading-none">+</span>}
          {creating ? "Vazgeç" : "Yeni ders"}
        </Button>
      </header>

      {/*
       * Liste ekranda dururken başarısız olan tazeleme. Eskiden yutuluyordu:
       * ders oluşturuluyor, ardından gelen `reload()` düşüyor ve kullanıcı
       * listede yeni dersi göremediği hâlde hiçbir açıklama almıyordu.
       */}
      {refreshError && (
        <div className="mb-6">
          <ErrorNote
            message={refreshError}
            kind={errorKind}
            requestId={errorRequestId}
            onRetry={reload}
          />
        </div>
      )}

      {creating && (
        <CreateCourseForm
          id={formId}
          onCreated={() => {
            setCreating(false);
            void reload();
          }}
        />
      )}

      {courses.length > 0 && (
        <section aria-label="Ders arama ve filtreler" className="mb-6">
          <div className="flex flex-col gap-5 border-b border-border pb-5 xl:flex-row xl:items-end xl:justify-between">
            <div className="w-full min-w-0 xl:max-w-md">
              <label htmlFor={searchId} className="mb-2 block text-sm font-medium text-fg">Derslerde ara</label>
              <div className="relative">
                <span aria-hidden="true" className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-[60%] rounded-full border-[1.5px] border-fg-muted after:absolute after:-bottom-1 after:-right-1 after:h-1.5 after:w-[1.5px] after:-rotate-45 after:rounded-full after:bg-fg-muted" />
                <input id={searchId} type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Ders adı veya kodu" className="h-12 w-full min-w-0 rounded-xl border border-border-strong bg-surface pr-4 pl-11 text-base text-fg placeholder:text-fg-subtle transition-[border-color,box-shadow] duration-250 hover:border-fg-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand" />
              </div>
            </div>
            <div role="group" aria-label="Ders rolü filtresi" className="flex max-w-full flex-wrap items-center gap-2">
              {([["all", "Tümü"], ["instructor", "Eğitmen"], ["student", "Öğrenci"]] as const).map(([value, label]) => (
                <button type="button" key={value} aria-pressed={roleFilter === value} onClick={() => setRoleFilter(value)} className={`inline-flex min-h-11 items-center justify-center rounded-xl border px-4 text-sm font-medium transition-[color,background-color,border-color] duration-250 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${roleFilter === value ? "border-brand/40 bg-brand-subtle text-brand" : "border-border bg-surface text-fg-muted hover:border-brand/40 hover:text-brand"}`}>{label}</button>
              ))}
            </div>
          </div>
          <p role="status" className="mt-4 text-sm text-fg-muted">
            {filteredCourses.length} ders gösteriliyor{nextCursor !== null ? ". Arama, yüklenen dersler içinde yapılır; diğer dersler için daha fazla yükleyin." : "."}
          </p>
        </section>
      )}

      {courses.length === 0 && !creating ? (
        <EmptyState title="Henüz dersiniz yok. Yeni ders açabilir veya eğitmeninizin sizi eklemesini bekleyebilirsiniz." />
      ) : filteredCourses.length === 0 && courses.length > 0 ? (
        <Card className="py-8 text-center">
          <p className="text-lg font-semibold text-fg">Aramanıza uygun ders bulunamadı.</p>
          <p className="mt-2 text-sm text-fg-muted">Başka bir ders adı deneyin veya filtreleri temizleyin.</p>
          <Button variant="secondary" className="mt-5" onClick={() => { setQuery(""); setRoleFilter("all"); }}>Filtreleri temizle</Button>
        </Card>
      ) : (
        <ul className="grid gap-5 xl:grid-cols-2">
          {filteredCourses.map((course, index) => (
            <li key={course.id} className={`min-w-0 rise rise-${Math.min(index + 1, 3)}`}>
              <Link href={`/courses/${course.id}`} className="group flex h-full min-w-0 flex-col overflow-hidden rounded-2xl border border-border bg-surface transition-[border-color,box-shadow,transform] duration-250 hover:-translate-y-1 hover:border-brand/40 hover:shadow-e2 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand motion-reduce:transform-none">
                <CourseCover title={course.title} code={course.code} className="border-b border-border" />
                <div className="flex min-w-0 flex-1 flex-col p-5 sm:p-6">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="min-w-0 font-mono text-sm font-medium text-brand [overflow-wrap:anywhere]">{course.code}</p>
                    <Badge tone={course.role === "instructor" ? "info" : "neutral"}>{course.role === "instructor" ? "Eğitmen" : "Öğrenci"}</Badge>
                  </div>
                  <h2 className="mt-3 flex-1 text-[1.5625rem] font-semibold leading-[1.22] tracking-[-0.04em] text-fg [overflow-wrap:anywhere]">{course.title}</h2>
                  <div aria-hidden="true" className="mt-5 flex min-h-11 items-center justify-between gap-4 text-sm">
                    <span className="text-fg-muted">{course.role === "instructor" ? "Ders çalışma alanı" : "Öğrenme alanı"}</span>
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-border-strong text-fg transition-[color,background-color,border-color] duration-250 group-hover:border-brand group-hover:bg-brand group-hover:text-white dark:group-hover:text-bg"><ChevronRightIcon size={20} /></span>
                  </div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
      <LoadMore
        hasMore={nextCursor !== null}
        busy={loadingMore}
        error={pageError}
        onLoadMore={() => void loadMore()}
      />
    </div>
  );
}

/**
 * Gönderim reddi: kullanıcıya gösterilecek metin ve bu reddin GİRİLEN DEĞERLE
 * ilgili olup olmadığı. İkisi tek durumda durur ki ayrışamasınlar — mesaj
 * güncellenip `aria-invalid` eski hâlinde kalırsa ekran okuyucu geçmiş bir
 * hatayı okur.
 */
interface Rejection {
  message: string;
  fromInput: boolean;
}

function CreateCourseForm({ id, onCreated }: { id: string; onCreated: () => void }) {
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [rejection, setRejection] = useState<Rejection | null>(null);
  const errorId = useId();

  /*
   * Buton `aria-disabled` ile beklemeye alınıyor, `disabled` ile değil:
   * `disabled` odağı `<body>`'ye atar (bkz. ui.tsx `Button`). `aria-disabled`
   * gönderimi kendiliğinden engellemediği için — ve Enter tuşu butona hiç
   * uğramadan formu gönderebildiği için — çift gönderim kapısı `useSubmit`'te
   * durur. Hata düz metin değil `Rejection` (mesaj + alan-geçersizliği), bu
   * yüzden kancanın kendi `error`'ı değil `onError` eşlemesi kullanılıyor.
   */
  const { busy, submit: create } = useSubmit(
    async () => {
      setRejection(null);
      await api.post("/courses", { code, title });
      onCreated();
    },
    {
      onError: (err) =>
        setRejection({
          message: errorMessage(err, "İşlem tamamlanamadı."),
          /* 4xx: sunucu girilen değerleri reddetti, alanlar gerçekten geçersiz.
             5xx ve ağ hatası girdinin suçu değil; alanı geçersiz işaretlemek
             kullanıcıya olmayan bir yazım hatası arattırır. */
          fromInput: err instanceof ApiError && err.status >= 400 && err.status < 500,
        }),
    },
  );

  function submit(e: React.FormEvent) {
    e.preventDefault();
    void create();
  }

  const describedBy = rejection ? errorId : undefined;
  const invalid = rejection?.fromInput ?? false;

  return (
    /* Çukur yüzey: form liste kartlarıyla aynı katmanda yarışmaz; "Oluştur"
       formun açık olduğu anda sayfadaki birincil eylemdir. */
    <Card variant="soft" className="mb-6">
      {/*
       * Etiketler görünür ve `htmlFor` ile bağlı; placeholder yalnız örnek
       * değerdir (DESIGN.md: "Placeholder metni etiket yerine kullanma —
       * odaklanınca kaybolur"). `sm:items-end` etiketli alanlarla butonu aynı
       * taban çizgisine oturtur; dar ekranda alanlar alt alta olduğu için
       * hizalama yalnız `sm`den itibaren uygulanır.
       */}
      <form
        id={id}
        onSubmit={submit}
        className="flex flex-col gap-4 sm:flex-row sm:items-end"
      >
        <div className="sm:w-40">
          <Field label="Ders kodu" describedBy={describedBy} invalid={invalid}>
            {(field) => (
              <Input
                {...field}
                /*
                 * Form yalnız kullanıcı "Yeni ders"e bastığında mount olur;
                 * odağı ilk alana taşımak burada sayfa açılışındaki odak
                 * hırsızlığı değil, açılan bölüme götüren normal davranıştır.
                 */
                autoFocus
                placeholder="örn. COME301"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
                minLength={2}
              />
            )}
          </Field>
        </div>
        <div className="flex-1">
          <Field label="Ders adı" describedBy={describedBy} invalid={invalid}>
            {(field) => (
              <Input
                {...field}
                placeholder="örn. İşletim Sistemleri"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
                minLength={2}
              />
            )}
          </Field>
        </div>
        <Button type="submit" aria-disabled={busy}>
          {busy ? "Oluşturuluyor…" : "Oluştur"}
        </Button>
      </form>
      {rejection && (
        <div id={errorId} className="mt-2">
          <ErrorNote message={rejection.message} />
        </div>
      )}
    </Card>
  );
}
