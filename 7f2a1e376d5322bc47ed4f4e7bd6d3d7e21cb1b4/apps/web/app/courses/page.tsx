"use client";

/** Ders listesi + ders açma (eğitmen). */

import Link from "next/link";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { useSession } from "@/lib/session";
import type { Course } from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { AppShell } from "@/components/app-shell";
import { Field } from "@/components/field";
import { ErrorNote, Loading, PageHeader } from "@/components/page-state";
import { Button, Card, EmptyState, Input } from "@/components/ui";

export default function CoursesPage() {
  return (
    <AppShell>
      <CourseList />
    </AppShell>
  );
}

function CourseList() {
  const [creating, setCreating] = useState(false);
  const { isInstructor } = useSession();
  const formId = useId();
  const toggleRef = useRef<HTMLButtonElement>(null);
  const opened = useRef(false);

  const fetchCourses = useCallback(() => api.get<Course[]>("/courses"), []);
  const {
    data: courses,
    error,
    refreshError,
    errorKind,
    errorRequestId,
    loading,
    reload,
  } = useResource(fetchCourses, []);

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

  return (
    <div>
      <PageHeader
        title="Derslerim"
        action={
          isInstructor && (
            <Button
              ref={toggleRef}
              variant="secondary"
              /* Düğme bir bölümü açıp kapatıyor; durum yalnız etiket
                 değişiminden değil, işaretten de okunmalı. */
              aria-expanded={creating}
              aria-controls={creating ? formId : undefined}
              onClick={() => setCreating((v) => !v)}
            >
              {creating ? "Vazgeç" : "Yeni ders"}
            </Button>
          )
        }
      />

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

      {courses.length === 0 && !creating ? (
        <EmptyState
          title={
            isInstructor
              ? "Henüz dersiniz yok. Yeni ders açarak materyal yüklemeye başlayın."
              : "Henüz bir derse kayıtlı değilsiniz. Eğitmeninizin sizi eklemesini bekleyin."
          }
        />
      ) : (
        /* Kart ızgarası bir listedir: `ul/li` ekran okuyucuya kaç ders
           olduğunu söyler, `div` yığını söylemez. */
        <ul className="grid gap-4 sm:grid-cols-2">
          {courses.map((course, index) => (
            <li key={course.id} className={`rise rise-${Math.min(index + 1, 3)}`}>
              <Link
                href={`/courses/${course.id}`}
                /* Odak halkası ürünün her tıklanabilir öğesinde aynı: kart
                   bağlantısı tarayıcı varsayılanına bırakılmaz. */
                className="block h-full rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
              >
                <Card className="h-full transition-[border,box-shadow] duration-200 hover:border-border-strong hover:shadow-[0_2px_8px_rgba(28,25,23,0.04)]">
                  <p className="font-mono text-xs tracking-wide text-fg-subtle">
                    {course.code}
                  </p>
                  <p className="mt-2 text-lg font-medium tracking-tight text-fg">
                    {course.title}
                  </p>
                  <p className="mt-4 text-xs text-fg-subtle">
                    {course.role === "instructor" ? "Eğitmen" : "Öğrenci"}
                  </p>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      )}
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
  const [busy, setBusy] = useState(false);
  const errorId = useId();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    /*
     * Buton `aria-disabled` ile beklemeye alınıyor, `disabled` ile değil:
     * `disabled` odağı `<body>`'ye atar (bkz. ui.tsx `Button`). `aria-disabled`
     * gönderimi kendiliğinden engellemediği için — ve Enter tuşu butona hiç
     * uğramadan formu gönderebildiği için — çift gönderim kapısı burada durur.
     */
    if (busy) return;
    setBusy(true);
    setRejection(null);
    try {
      await api.post("/courses", { code, title });
      onCreated();
    } catch (err) {
      setRejection({
        message: errorMessage(err, "İşlem tamamlanamadı."),
        /* 4xx: sunucu girilen değerleri reddetti, alanlar gerçekten geçersiz.
           5xx ve ağ hatası girdinin suçu değil; alanı geçersiz işaretlemek
           kullanıcıya olmayan bir yazım hatası arattırır. */
        fromInput: err instanceof ApiError && err.status >= 400 && err.status < 500,
      });
    } finally {
      setBusy(false);
    }
  }

  const describedBy = rejection ? errorId : undefined;
  const invalid = rejection?.fromInput ?? false;

  return (
    <Card className="mb-6">
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
        className="flex flex-col gap-3 sm:flex-row sm:items-end"
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
