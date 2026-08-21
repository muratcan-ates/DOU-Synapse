import { describe, expect, test } from "bun:test";

import { canDismissConfirmAction } from "../components/ui";

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

describe("ConfirmAction işlem yarışı", () => {
  test("işlem sürerken Vazgeç onay satırını kapatmaz", async () => {
    let confirming = true;
    let busy = false;
    const request = deferred();

    const confirm = async () => {
      busy = true;
      await request.promise;
      confirming = false;
      busy = false;
    };
    const cancel = () => {
      if (!canDismissConfirmAction(busy)) return;
      confirming = false;
    };

    const pending = confirm();
    cancel();

    expect(busy).toBe(true);
    expect(confirming).toBe(true);

    request.resolve();
    await pending;
    expect(confirming).toBe(false);
  });

  test("Vazgeç butonu saf kapıyı ve aria-disabled durumunu gerçekten kullanır", async () => {
    const source = await Bun.file(
      new URL("../components/ui.tsx", import.meta.url),
    ).text();

    expect(source).toContain('aria-disabled={busy}');
    expect(source).toContain("if (!canDismissConfirmAction(busy)) return;");
  });
});
