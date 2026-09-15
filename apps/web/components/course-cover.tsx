import { courseCoverDesign, type CourseCoverInput } from "@/lib/course-cover";

const SURFACES = [
  "bg-brand-subtle text-brand",
  "bg-surface-sunken text-fg",
  "bg-surface text-fg",
] as const;

/** Decorative initials cover; the adjacent real course title names the link. */
export function CourseCover({
  title,
  code,
  size = "tile",
  className = "",
}: CourseCoverInput & {
  size?: "tile" | "compact" | "feature";
  className?: string;
}) {
  const design = courseCoverDesign({ title, code });
  const compact = size === "compact";
  const sizing = compact
    ? "h-12 w-12 shrink-0 rounded-xl text-xl"
    : size === "feature"
      ? "h-full w-full rounded-2xl text-[4.5rem] sm:text-[5.5rem]"
      : "h-32 w-full text-[4.25rem] sm:h-36 sm:text-[4.75rem]";

  return (
    <div aria-hidden="true" style={{ containerType: "inline-size" }} className={`pointer-events-none relative isolate flex min-w-0 items-center overflow-hidden select-none ${SURFACES[design.layout]} ${sizing} ${className}`}>
      <span
        className={`absolute aspect-square w-[68%] rounded-[18%] border border-brand/25 ${design.layout === 2 ? "bg-brand-subtle/60" : "bg-surface/30"}`}
        style={{ right: `${-design.offset}%`, top: "-24%", transform: `rotate(${design.rotation + 24}deg)` }}
      />
      <span
        className="absolute aspect-square w-[58%] rounded-[12%] border border-brand/20"
        style={{ right: `${design.offset - 18}%`, bottom: "-44%", transform: `rotate(${design.rotation - 12}deg)` }}
      />
      {!compact && (
        <>
          <span className="absolute top-5 h-px w-8 bg-brand/45" style={{ left: `${design.offset}%` }} />
          <span className="absolute right-5 bottom-5 h-5 w-px bg-brand/30" />
          <span className="absolute right-5 bottom-5 h-px w-5 bg-brand/30" />
        </>
      )}
      <span
        className={`relative z-10 block font-semibold leading-none tracking-[-0.075em] ${compact ? "w-full text-center" : "pb-1"}`}
        style={compact ? undefined : { marginLeft: `${design.offset}%`, ...(size === "feature" ? { fontSize: "clamp(32px, 30cqw, 88px)" } : {}) }}
      >
        {design.initials}
      </span>
    </div>
  );
}
