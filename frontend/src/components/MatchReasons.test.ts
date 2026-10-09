import { describe, expect, it } from "vitest";
import { matchReasonsText } from "./MatchReasons";

describe("matchReasonsText", () => {
  it("merinci poin sampai jumlahnya = skor", () => {
    expect(
      matchReasonsText({
        match_score: 85,
        explain: "skill cocok: las",
        explain_source: "rules",
        reasons: [
          { label: "Skill cocok: las", points: 70 },
          { label: "Domisili cocok (Surabaya)", points: 8 },
          { label: "Ekspektasi gaji dalam rentang", points: 7 },
          { label: "Ekspektasi gaji di luar rentang", points: 0 },
        ],
        missing: [],
      })
    ).toBe(
      "Skill cocok: las +70 · Domisili cocok (Surabaya) +8 · Ekspektasi gaji dalam rentang +7 · Ekspektasi gaji di luar rentang 0 = 85"
    );
  });

  it("memberi label kalimat AI dan persyaratan yang kurang", () => {
    expect(
      matchReasonsText({
        match_score: 100,
        explain: "Pengalaman relevan.",
        explain_source: "ai",
        reasons: [
          { label: "Kemiripan profil dengan job order (100%)", points: 80 },
          { label: "Bonus", points: 30 },
          { label: "Dibatasi maksimum 100", points: -10 },
        ],
        missing: ["sertifikasi K3"],
      })
    ).toBe(
      "Kemiripan profil dengan job order (100%) +80 · Bonus +30 · Dibatasi maksimum 100 -10 = 100\nAI: Pengalaman relevan.\nKurang: sertifikasi K3"
    );
  });

  it("respons lama tanpa reasons jatuh ke explain", () => {
    expect(matchReasonsText({ match_score: 60, explain: "kecocokan umum", missing: [] })).toBe("kecocokan umum");
  });
});
