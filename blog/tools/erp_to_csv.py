#!/usr/bin/env python3
"""ERP 백업(JSON)에서 블로그 글감용 공연 목록(CSV)을 만든다.

사용법: python3 -I blog/tools/erp_to_csv.py <ERP 백업 JSON> [기준일 YYYY-MM-DD]

ERP 설정 탭의 [JSON 백업 저장]으로 받은 파일의 '복사본'을 읽기만 한다.
원본 파일은 바꾸지 않고, 결과는 같은 폴더에 공연목록_<기준일>.csv로 따로 저장한다.

블로그에 쓰면 안 되는 정보는 처음부터 CSV에 넣지 않는다.
- 빼는 것: 기관 이름, 담당자, 연락처, 이메일, 주소, 금액, 정산·계산서·사업자 정보
- 빼는 공연: 취소 상태, 테스트로 넣은 기록
- 메모에 섞인 전화번호·이메일·금액은 지운다.
"""
import csv
import datetime
import json
import os
import re
import sys

# 기관 이름 속 단어로 기관 유형을 정한다. 위에서부터 먼저 맞는 것을 쓴다.
ORG_RULES = [
    ("어린이집", "어린이집"),
    ("유치원", "유치원"),
    ("초등학교", "초등학교"),
    ("중학교", "중학교"),
    ("고등학교", "고등학교"),
    ("도서관", "도서관"),
    ("태권도", "태권도장"),
    ("주민센터", "주민센터"),
    ("복지관", "복지관"),
    ("구청", "지자체"),
    ("시청", "지자체"),
    ("군청", "지자체"),
    ("재단", "지자체·공공기관"),
    ("공원", "지자체·공공 행사"),
    ("축제", "축제"),
    ("교회", "교회"),
    ("마켓", "마켓·야외 행사"),
    ("키자니아", "어린이 체험시설"),
]
# 실적 기업명: 글에 쓰려면 글마다 대표님 확인이 필요하다(brand-and-rules.md).
NAMED_CLIENTS = ["키자니아", "삼성", "현대캐피코", "현대케피코", "KB"]

PHONE_RE = re.compile(r"0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
MONEY_RE = re.compile(r"\d[\d,]*\s*(?:만\s?원|천\s?원|원)|₩\s*\d[\d,]*|\d{1,3}(?:,\d{3})+")

WEEKDAYS = "월화수목금토일"

COLUMNS = ["날짜", "요일", "쓰임", "ERP상태", "기관유형", "지역", "공연종류", "회차·메모",
           "공연자", "문의경로", "확인필요"]


def org_type(client):
    name = (client or "").replace(" ", "")
    for word, label in ORG_RULES:
        if word in name:
            return label
    return "기타"


def clean_memo(memo):
    text = str(memo or "")
    text = PHONE_RE.sub("", text)
    text = EMAIL_RE.sub("", text)
    text = MONEY_RE.sub("", text)
    return re.sub(r"\s{2,}", " ", text).strip(" /,·")


def usage_of(status, show_date, today):
    if status == "완료":
        return "후기"
    if status == "확정":
        return "예정 안내" if show_date >= today else "후기 후보(완료 확인 필요)"
    return ""


def convert(src_path, today):
    with open(src_path, encoding="utf-8") as f:  # 읽기만 한다
        data = json.load(f)
    shows = data.get("shows")
    if not isinstance(shows, list):
        raise SystemExit("ERP 백업 파일이 아닌 것 같습니다 (shows 목록이 없음).")

    rows, skipped = [], {"취소": 0, "테스트": 0, "상태 모름": 0}
    for s in shows:
        status = str(s.get("status", "")).strip()
        client = str(s.get("client", ""))
        if status == "취소":
            skipped["취소"] += 1
            continue
        if "테스트" in client or client.strip().lower() == "test":
            skipped["테스트"] += 1
            continue
        date = str(s.get("showDate", "")).strip()[:10]
        use = usage_of(status, date, today)
        if not use:
            skipped["상태 모름"] += 1
            continue

        checks = []
        org = org_type(client)
        if org == "기타":
            checks.append("기관 유형 확인")
        if any(n in client for n in NAMED_CLIENTS):
            checks.append("실적 기업명이라 공개 여부 확인")
        if use.startswith("후기 후보"):
            checks.append("ERP에서 완료로 바꿨는지 확인")

        try:
            wd = WEEKDAYS[datetime.date.fromisoformat(date).weekday()]
        except ValueError:
            wd = ""
            checks.append("날짜 형식 확인")

        performer = str(s.get("performer", "")).strip()
        rows.append({
            "날짜": date,
            "요일": wd,
            "쓰임": use,
            "ERP상태": status,
            "기관유형": org,
            "지역": str(s.get("region", "")).strip(),
            "공연종류": str(s.get("theme", "")).strip(),
            "회차·메모": clean_memo(s.get("memo")),
            "공연자": "버블케이" if performer == "버블케이" else ("다른 공연자" if performer else ""),
            "문의경로": str(s.get("channel", "")).strip(),
            "확인필요": " / ".join(checks),
        })

    rows.sort(key=lambda r: r["날짜"])
    out_path = os.path.join(os.path.dirname(os.path.abspath(src_path)), f"공연목록_{today}.csv")
    if os.path.abspath(out_path) == os.path.abspath(src_path):
        raise SystemExit("결과 파일이 원본과 같은 이름이라 멈춥니다.")
    # utf-8-sig: Windows 엑셀에서 열어도 한글이 깨지지 않게 한다
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return out_path, rows, skipped


def main(argv):
    if len(argv) not in (2, 3):
        print(__doc__)
        return 2
    today = argv[2] if len(argv) == 3 else datetime.date.today().isoformat()
    out_path, rows, skipped = convert(argv[1], today)
    counts = {}
    for r in rows:
        counts[r["쓰임"]] = counts.get(r["쓰임"], 0) + 1
    print(f"저장: {out_path}")
    print(f"기준일: {today}, 담은 공연 {len(rows)}건 " + str(counts))
    print("뺀 공연: " + ", ".join(f"{k} {v}건" for k, v in skipped.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
