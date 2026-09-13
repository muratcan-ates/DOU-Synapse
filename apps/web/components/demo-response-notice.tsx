import { DEMO_RESPONSE_LABEL } from "@/lib/demo-response";
import { Badge } from "@/components/ui";

/** Demo kökenini yalnız sunucunun açık bildirimiyle gösterir. */
export function DemoResponseNotice({ fixture }: { fixture?: true | null }) {
  if (fixture !== true) return null;
  return <p><Badge tone="info">{DEMO_RESPONSE_LABEL}</Badge></p>;
}
