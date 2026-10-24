#!/usr/bin/env python3
"""블로그 초안 점검 스크립트.

사용법: python3 -I scripts/check_draft.py <초안 파일.txt>

초안은 [제목 후보] / [본문] / [태그] / [대표님 확인 필요] 구간으로 나뉜 텍스트 파일이다.
제목 후보와 본문 구간만 '네이버 에디터에 붙는 글'로 보고 검사한다.

검사 항목
- 마크다운 기호(#, **, - 목록, 표 |, ``` 등)와 장식선이 남아 있지 않은지
  (네이버 에디터에 붙이면 기호가 그대로 보이기 때문)
- 문의처(전화·이메일)가 본문에 있고, 글의 맨 끝쪽에 놓였는지
- [ ]로 비워 둔 자리표시가 없는지 (사진 자리 [사진1: ...]은 허용)
- 이츠쇼 번호가 아닌 전화번호(고객 연락처 유출 가능성)와 금액이 없는지
- '단독 공연' 표현이 없는지

FAIL이 하나라도 있으면 종료 코드 1로 끝난다.
"""
import re
import sys

COMPANY_PHONE = "010-2485-8561"
COMPANY_EMAIL = "itsshow001@naver.com"

HEADER_RE = re.compile(
    r"^\[(제목 후보|본문|태그|대표님 확인 필요|작성 메모|작성 가정|글 종류|작성일)[^\]]*\]"
)


DECOR_RE = re.compile(r"^\s*([=\-*_~])\1{2,}\s*$")


def trim_edges(lines):
    """구간 맨 앞뒤의 빈 줄과 장식선(=====)을 뺀다. 헤더를 꾸미는 선은 붙여넣는 글이 아니기 때문이다."""
    lines = list(lines)
    while lines and (not lines[0].strip() or DECOR_RE.match(lines[0])):
        lines.pop(0)
    while lines and (not lines[-1].strip() or DECOR_RE.match(lines[-1])):
        lines.pop()
    return lines


def split_sections(text):
    """헤더 줄([본문] 등)을 기준으로 구간을 나눈다. 헤더 앞의 내용은 '' 구간."""
    sections = {}
    current = ""
    for line in text.splitlines():
        m = HEADER_RE.match(line.strip())
        if m:
            current = m.group(1)
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {k: trim_edges(v) for k, v in sections.items()}


def main(path):
    text = open(path, encoding="utf-8").read()
    sections = split_sections(text)

    has_body_header = "본문" in sections
    if not has_body_header:
        print("WARN  [본문] 구간 표시가 없어 파일 전체를 검사합니다.")
        scan_lines = text.splitlines()
        body_lines = scan_lines
    else:
        scan_lines = sections.get("제목 후보", []) + sections["본문"]
        body_lines = sections["본문"]

    results = []  # (level, message)

    # 1) 마크다운·장식 기호
    md_rules = [
        (re.compile(r"^\s{0,3}#{1,6}\s"), "제목 기호(#)"),
        (re.compile(r"\*\*|__"), "굵은 글씨 기호(** 또는 __)"),
        (re.compile(r"^\s*[-*+]\s+\S"), "목록 기호(-, *, +)"),
        (re.compile(r"^\s*\|.*\|\s*$"), "표 기호(|)"),
        (re.compile(r"```"), "코드 블록 기호(```)"),
        (re.compile(r"`"), "백틱(`)"),
        (re.compile(r"^\s*>\s"), "인용 기호(>)"),
        (re.compile(r"\[[^\]]+\]\(https?://"), "마크다운 링크"),
        (re.compile(r"^\s*([=\-*_~])\1{2,}\s*$"), "장식선(=== --- *** 등)"),
    ]
    md_hits = []
    for i, line in enumerate(scan_lines, 1):
        for rx, label in md_rules:
            if rx.search(line):
                md_hits.append(f"  - {label}: {line.strip()[:50]}")
                break
    if md_hits:
        results.append(("FAIL", "붙여넣을 글에 기호가 남아 있습니다:\n" + "\n".join(md_hits[:10])))
    else:
        results.append(("OK", "마크다운·장식 기호가 없습니다."))

    body_text = "\n".join(body_lines)
    scan_text = "\n".join(scan_lines)

    # 2) 문의처
    missing = [name for name, val in (("전화", COMPANY_PHONE), ("이메일", COMPANY_EMAIL)) if val not in body_text]
    if missing:
        results.append(("FAIL", "본문에 문의처가 빠졌습니다: " + ", ".join(missing)))
    else:
        non_empty = [l for l in body_lines if l.strip()]
        tail = "\n".join(non_empty[-15:])
        if COMPANY_PHONE in tail or COMPANY_EMAIL in tail:
            results.append(("OK", "문의처(전화·이메일)가 본문 끝쪽에 있습니다."))
        else:
            results.append(("WARN", "문의처는 있지만 글의 끝쪽이 아닙니다. 맨 끝으로 옮겨 주세요."))

    # 3) 빈칸 자리표시
    ph_rx = re.compile(r"\[[^\]]*(삽입|입력|넣기|채우|TODO|확인 필요|확인 후|※)[^\]]*\]")
    ph_hits = [m.group(0) for m in ph_rx.finditer(scan_text)]
    if ph_hits:
        results.append(("FAIL", "채우지 않은 자리표시가 있습니다: " + ", ".join(ph_hits[:5])))
    else:
        results.append(("OK", "빈칸 자리표시가 없습니다."))
    if re.search(r"○○|OOO|XXX|OO어린이집", scan_text):
        results.append(("WARN", "'○○' 같은 임시 표시가 남아 있습니다."))

    # 4) 이츠쇼 번호가 아닌 전화번호
    phones = set(re.findall(r"0\d{1,2}-\d{3,4}-\d{4}", scan_text))
    others = sorted(p for p in phones if p != COMPANY_PHONE)
    if others:
        results.append(("FAIL", "이츠쇼가 아닌 전화번호가 있습니다(고객 연락처일 수 있음): " + ", ".join(others)))
    else:
        results.append(("OK", "다른 전화번호가 없습니다."))

    # 5) 금액
    money = re.findall(r"\d[\d,]*\s*(?:만\s?원|원)", scan_text)
    if money:
        results.append(("WARN", "금액처럼 보이는 표현이 있습니다: " + ", ".join(money[:5]) + " (공연 금액이면 삭제)"))

    # 6) 금지 표현
    if "단독 공연" in scan_text:
        results.append(("FAIL", "'단독 공연'은 쓰지 않습니다. '콜라보 공연'으로 바꿔 주세요."))

    failed = False
    for level, msg in results:
        print(f"{level:5} {msg}")
        if level == "FAIL":
            failed = True
    print("\n결과:", "수정이 필요합니다." if failed else "통과")
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
