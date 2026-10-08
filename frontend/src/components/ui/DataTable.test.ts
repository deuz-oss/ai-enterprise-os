import { describe, expect, it } from "vitest";
import { sortRows } from "./DataTable";
import { currentPeriod } from "./PeriodPicker";

interface Row {
  no: string;
  amount: number | null;
}

const rows: Row[] = [
  { no: "EMP-10", amount: 500 },
  { no: "EMP-2", amount: null },
  { no: "EMP-1", amount: 2000 },
  { no: "", amount: 50 },
];

describe("sortRows", () => {
  it("teks memakai urutan numerik (EMP-2 sebelum EMP-10)", () => {
    expect(sortRows(rows, (r) => r.no, "asc").map((r) => r.no)).toEqual(["EMP-1", "EMP-2", "EMP-10", ""]);
  });

  it("angka diurutkan numerik, bukan string", () => {
    expect(sortRows(rows, (r) => r.amount, "desc").map((r) => r.amount)).toEqual([2000, 500, 50, null]);
  });

  it("nilai kosong tetap di akhir pada kedua arah", () => {
    const asc = sortRows(rows, (r) => r.amount, "asc");
    const desc = sortRows(rows, (r) => r.no, "desc");
    expect(asc[asc.length - 1].amount).toBeNull();
    expect(desc[desc.length - 1].no).toBe("");
  });

  it("tidak mengubah array asli", () => {
    const before = rows.map((r) => r.no);
    sortRows(rows, (r) => r.no, "desc");
    expect(rows.map((r) => r.no)).toEqual(before);
  });
});

describe("currentPeriod", () => {
  it("mengikuti tanggal berjalan (bukan hardcode)", () => {
    const now = new Date();
    expect(currentPeriod()).toEqual({ year: now.getFullYear(), month: now.getMonth() + 1 });
  });
});
