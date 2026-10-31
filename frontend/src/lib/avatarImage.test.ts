import { describe, expect, it } from "vitest";
import {
  AVATAR_ACCEPT_ATTR,
  AVATAR_MAX_BYTES,
  validateAvatarDimensions,
  validateAvatarFileMeta,
} from "./avatarImage";

describe("validateAvatarFileMeta", () => {
  it("menerima JPEG, PNG, dan WebP dalam batas ukuran", () => {
    for (const type of ["image/jpeg", "image/png", "image/webp"]) {
      expect(validateAvatarFileMeta({ type, size: 200_000 })).toBeNull();
    }
  });

  it("menolak format lain (GIF, SVG, PDF, tanpa tipe)", () => {
    for (const type of ["image/gif", "image/svg+xml", "application/pdf", ""]) {
      expect(validateAvatarFileMeta({ type, size: 1000 })).toMatch(/Format tidak didukung/);
    }
  });

  it("menerima tepat 5 MB, menolak lebih dari itu", () => {
    expect(validateAvatarFileMeta({ type: "image/png", size: AVATAR_MAX_BYTES })).toBeNull();
    expect(validateAvatarFileMeta({ type: "image/png", size: AVATAR_MAX_BYTES + 1 })).toMatch(
      /melebihi batas 5 MB/
    );
  });

  it("menolak file kosong", () => {
    expect(validateAvatarFileMeta({ type: "image/jpeg", size: 0 })).toMatch(/kosong/);
  });
});

describe("validateAvatarDimensions", () => {
  it("menerima tepat 256×256 dan lebih besar", () => {
    expect(validateAvatarDimensions(256, 256)).toBeNull();
    expect(validateAvatarDimensions(1024, 768)).toBeNull();
  });

  it("menolak bila salah satu sisi di bawah 256 px", () => {
    expect(validateAvatarDimensions(255, 512)).toMatch(/255×512 px terlalu kecil/);
    expect(validateAvatarDimensions(512, 200)).toMatch(/Minimal 256×256 px/);
  });
});

describe("AVATAR_ACCEPT_ATTR", () => {
  it("sama dengan atribut accept pada input file", () => {
    expect(AVATAR_ACCEPT_ATTR).toBe("image/jpeg,image/png,image/webp");
  });
});
