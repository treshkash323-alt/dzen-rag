from pathlib import Path

base = Path(r"G:\3_Дзен\1G_канал про ИИ_статьи на Дзене\4_AIKIVAVIORA_база-RAG\модуль 1.3 - 24.05.2026")
out = Path(r"C:\Users\kash-\Python_kash\Cursor\AIKIVAVIORA_v.3_Cursor\00docs\_rag_1_3_inventory.txt")
lines = [f"=== {base} ===", f"exists: {base.is_dir()}", ""]
count = 0
if base.is_dir():
    for p in sorted(base.rglob("*")):
        rel = p.relative_to(base)
        if p.is_dir():
            lines.append(f"[DIR] {rel}/")
        else:
            count += 1
            lines.append(f"{p.stat().st_size:>10,}  {rel}")
lines.append("")
lines.append(f"Total files: {count}")
out.write_text("\n".join(lines), encoding="utf-8")
print(out)
print("files", count)
