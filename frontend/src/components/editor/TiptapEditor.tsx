import { useEffect, useState, type CSSProperties } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import TaskList from "@tiptap/extension-task-list";
import TaskItem from "@tiptap/extension-task-item";
import "./editorStyles.css";

interface Props {
  /** HTML terkontrol; dimuat ulang saat pageKey berubah. */
  html: string;
  /** Kunci identitas halaman — pindah halaman me-reset isi editor. */
  pageKey: string;
  editable: boolean;
  placeholder?: string;
  onChange?: (html: string) => void;
}

interface SlashState {
  from: number;
}

/// Fase D — block editor TipTap: toolbar minimal + slash command "/".
export default function TiptapEditor({
  html,
  pageKey,
  editable,
  placeholder = "Tulis '/' untuk blok, atau mulai mengetik…",
  onChange,
}: Props) {
  const [slash, setSlash] = useState<SlashState | null>(null);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ heading: { levels: [1, 2, 3] } }),
      Placeholder.configure({ placeholder }),
      TaskList,
      TaskItem.configure({ nested: true }),
    ],
    content: html || "<p></p>",
    editable,
    onUpdate({ editor: ed }) {
      onChange?.(ed.getHTML());
      // Slash command: deteksi karakter "/" sendirian tepat sebelum caret.
      const sel = ed.state.selection;
      const before = ed.state.doc.textBetween(
        Math.max(0, sel.from - 1),
        sel.from,
        "\n",
        "\n"
      );
      setSlash(before === "/" ? { from: sel.from } : null);
    },
  });

  // Pindah halaman → muat ulang konten.
  useEffect(() => {
    if (editor) editor.commands.setContent(html || "<p></p>");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageKey]);

  // Toggle pratinjau/edit.
  useEffect(() => {
    if (editor) editor.setEditable(editable);
  }, [editable, editor]);

  if (!editor) return null;
  // Snapshot non-null agar narrowing bertahan di dalam closure di bawah.
  const inst: NonNullable<ReturnType<typeof useEditor>> = editor;

  const runWith = (clearSlash: boolean) =>
    (run: (c: import("@tiptap/core").ChainedCommands) => void) => {
      let chain = inst.chain().focus();
      if (clearSlash && slash) {
        chain = chain.deleteRange({ from: slash.from - 1, to: slash.from });
      }
      run(chain);
      setSlash(null);
    };

  const btn = (active: boolean): CSSProperties => ({
    borderRadius: 4,
    padding: "3px 8px",
    fontSize: 12.5,
    fontWeight: active ? 600 : 400,
    color: active ? "#ffffff" : "var(--text-muted)",
    backgroundColor: active ? "var(--accent)" : "transparent",
  });

  return (
    <div className="aeos-prose">
      {editable && (
        <div
          className="mb-2 flex flex-wrap items-center gap-0.5 rounded-md px-1 py-1"
          style={{ border: "1px solid var(--border)", backgroundColor: "var(--bg-elevated)" }}
        >
          <button style={btn(inst.isActive("heading", { level: 1 }))} onClick={() => runWith(false)((c) => c.toggleHeading({ level: 1 }).run())}>
            H1
          </button>
          <button style={btn(inst.isActive("heading", { level: 2 }))} onClick={() => runWith(false)((c) => c.toggleHeading({ level: 2 }).run())}>
            H2
          </button>
          <button style={btn(inst.isActive("heading", { level: 3 }))} onClick={() => runWith(false)((c) => c.toggleHeading({ level: 3 }).run())}>
            H3
          </button>
          <span style={{ width: 6 }} />
          <button style={btn(inst.isActive("bold"))} onClick={() => runWith(false)((c) => c.toggleBold().run())}>
            B
          </button>
          <button style={btn(inst.isActive("italic"))} onClick={() => runWith(false)((c) => c.toggleItalic().run())}>
            <i>I</i>
          </button>
          <span style={{ width: 6 }} />
          <button style={btn(inst.isActive("bulletList"))} onClick={() => runWith(false)((c) => c.toggleBulletList().run())}>
            • List
          </button>
          <button style={btn(inst.isActive("orderedList"))} onClick={() => runWith(false)((c) => c.toggleOrderedList().run())}>
            1. List
          </button>
          <button style={btn(inst.isActive("taskList"))} onClick={() => runWith(false)((c) => c.toggleTaskList().run())}>
            ☑ Todo
          </button>
          <span style={{ width: 6 }} />
          <button style={btn(inst.isActive("blockquote"))} onClick={() => runWith(false)((c) => c.toggleBlockquote().run())}>
            ❝ Callout
          </button>
          <button style={btn(false)} onClick={() => runWith(false)((c) => c.setHorizontalRule().run())}>
            ― Divider
          </button>
        </div>
      )}

      <div className="relative">
        <EditorContent editor={inst} />
        {editable && slash && (
          <div
            className="absolute left-2 top-10 z-20 w-56 overflow-hidden rounded-lg py-1 shadow-lg"
            style={{
              backgroundColor: "var(--bg-elevated)",
              border: "1px solid var(--border)",
            }}
          >
            <p
              className="px-3 pb-1 pt-1 text-[10.5px] font-semibold uppercase tracking-wide"
              style={{ color: "var(--text-muted)" }}
            >
              Blok
            </p>
            {[
              { label: "Heading 1", emoji: "🅷", run: () => runWith(true)((c) => c.toggleHeading({ level: 1 }).run()) },
              { label: "Heading 2", emoji: "🅷", run: () => runWith(true)((c) => c.toggleHeading({ level: 2 }).run()) },
              { label: "Heading 3", emoji: "🅷", run: () => runWith(true)((c) => c.toggleHeading({ level: 3 }).run()) },
              { label: "Bullet list", emoji: "•", run: () => runWith(true)((c) => c.toggleBulletList().run()) },
              { label: "Numbered list", emoji: "1.", run: () => runWith(true)((c) => c.toggleOrderedList().run()) },
              { label: "To-do list", emoji: "☑", run: () => runWith(true)((c) => c.toggleTaskList().run()) },
              { label: "Quote / Callout", emoji: "❝", run: () => runWith(true)((c) => c.toggleBlockquote().run()) },
              { label: "Divider", emoji: "―", run: () => runWith(true)((c) => c.setHorizontalRule().run()) },
            ].map((m) => (
              <button
                key={m.label}
                onClick={m.run}
                className="flex w-full items-center gap-2.5 px-3 py-1.5 text-left text-sm transition-colors hover:bg-[var(--hover)]"
                style={{ color: "var(--text)" }}
              >
                <span className="w-5 text-center">{m.emoji}</span>
                {m.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {!editable && (
        <p className="mt-2 text-[11px]" style={{ color: "var(--text-muted)" }}>
          Mode pratinjau — klik “Ubah” untuk menyunting.
        </p>
      )}
    </div>
  );
}
