import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import {
  BLACKLIST_BADGE_DESCRIPTION,
  BlacklistBadge,
  BlacklistToggle,
  canIncludeBlacklisted,
} from "./BlacklistBadge";

describe("BlacklistBadge", () => {
  it("menampilkan teks 'Blacklist' bertone danger + penjelasan untuk tooltip & screen reader", () => {
    const html = renderToStaticMarkup(<BlacklistBadge />);
    expect(html).toContain("p-red");
    expect(html).toContain(">Blacklist<");
    expect(html).toContain(`title="${BLACKLIST_BADGE_DESCRIPTION}"`);
    expect(html).toContain('class="sr-only"');
    // Ikon dekoratif tidak dibacakan.
    expect(html).toContain('aria-hidden="true"');
  });

  it("ukuran sm memakai teks lebih kecil untuk kartu padat", () => {
    expect(renderToStaticMarkup(<BlacklistBadge size="sm" />)).toContain("text-[10px]");
  });
});

describe("canIncludeBlacklisted", () => {
  it("hanya recruiter, management, dan admin", () => {
    expect(canIncludeBlacklisted("recruiter")).toBe(true);
    expect(canIncludeBlacklisted("management")).toBe(true);
    expect(canIncludeBlacklisted("admin")).toBe(true);
    expect(canIncludeBlacklisted("hr")).toBe(false);
    expect(canIncludeBlacklisted("operations")).toBe(false);
    expect(canIncludeBlacklisted("karyawan")).toBe(false);
    expect(canIncludeBlacklisted(undefined)).toBe(false);
    expect(canIncludeBlacklisted(null)).toBe(false);
  });
});

describe("BlacklistToggle", () => {
  it("checkbox terbungkus label berteks (aksesibel tanpa aria-label terpisah)", () => {
    const html = renderToStaticMarkup(<BlacklistToggle checked onChange={() => {}} />);
    expect(html).toMatch(/^<label[^>]*>.*<input type="checkbox" checked="".*Tampilkan kandidat blacklist<\/label>$/);
  });
});
