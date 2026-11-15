"""Generate small multi-page demo documents in English, Russian and Arabic."""
import subprocess
from pathlib import Path

from docx import Document

HERE = Path(__file__).parent

EN = [
    ("Solar Energy: An Overview", [
        "Solar energy is the radiant light and heat from the Sun that is harnessed using technologies such as "
        "photovoltaic (PV) panels and solar thermal collectors. It is one of the fastest-growing sources of "
        "renewable electricity in the world.",
        "A photovoltaic cell converts sunlight directly into electricity using the photovoltaic effect, which "
        "was first observed by the French physicist Edmond Becquerel in 1839. Most commercial cells today are "
        "made of crystalline silicon.",
    ]),
    ("Efficiency and Cost", [
        "The efficiency of a solar panel is the share of sunlight energy that it converts into electricity. "
        "Typical commercial silicon panels reach an efficiency of about 20 to 23 percent, while laboratory "
        "multi-junction cells have exceeded 45 percent.",
        "The cost of solar modules has fallen by roughly 90 percent between 2010 and 2020, mainly because of "
        "mass production, improved manufacturing and economies of scale.",
    ]),
    ("Challenges", [
        "The main challenge of solar power is intermittency: panels produce no electricity at night and less "
        "on cloudy days. Battery storage systems, such as lithium-ion batteries, are used to store surplus "
        "energy for later use.",
        "Another challenge is land use for large solar farms. Rooftop installations and agrivoltaics, which "
        "combine agriculture with solar panels on the same land, help to reduce this problem.",
    ]),
]

RU = [
    ("Московский метрополитен", [
        "Московский метрополитен был открыт 15 мая 1935 года. Первая линия соединяла станции «Сокольники» и "
        "«Парк культуры» и имела длину около 11 километров.",
        "Сегодня московское метро является одним из самых загруженных в мире: в обычный рабочий день им "
        "пользуются миллионы пассажиров.",
    ]),
    ("Архитектура станций", [
        "Многие станции московского метро известны своей архитектурой. Станции «Маяковская» и "
        "«Комсомольская» украшены мозаиками, мрамором и люстрами и считаются памятниками архитектуры.",
        "Станция «Маяковская» получила главный приз на Всемирной выставке в Нью-Йорке в 1939 году.",
    ]),
    ("Развитие сети", [
        "В 2016 году было открыто Московское центральное кольцо (МЦК), а в 2023 году была полностью завершена "
        "Большая кольцевая линия, ставшая одной из самых длинных кольцевых линий метро в мире.",
        "Интервал движения поездов в часы пик на многих линиях составляет около 90 секунд.",
    ]),
]

AR = [
    ("الذكاء الاصطناعي", [
        "الذكاء الاصطناعي هو فرع من علوم الحاسوب يهدف إلى بناء أنظمة قادرة على أداء مهام تتطلب عادة "
        "ذكاءً بشرياً، مثل فهم اللغة والتعرف على الصور واتخاذ القرارات.",
        "صاغ العالم جون مكارثي مصطلح الذكاء الاصطناعي عام 1956 خلال مؤتمر دارتموث في الولايات المتحدة.",
    ]),
    ("تعلم الآلة", [
        "تعلم الآلة هو أحد مجالات الذكاء الاصطناعي، ويعتمد على تدريب النماذج باستخدام البيانات بدلاً من "
        "كتابة القواعد يدوياً. ومن أشهر أنواعه التعلم الخاضع للإشراف والتعلم غير الخاضع للإشراف.",
        "التعلم العميق يستخدم شبكات عصبية متعددة الطبقات، وقد حقق نتائج كبيرة في الترجمة الآلية "
        "والتعرف على الكلام.",
    ]),
    ("معالجة اللغات الطبيعية", [
        "معالجة اللغات الطبيعية تمكّن الحاسوب من فهم النصوص البشرية وتوليدها. ومن تطبيقاتها أنظمة "
        "الإجابة عن الأسئلة والتلخيص الآلي والترجمة.",
        "تعتبر اللغة العربية من اللغات الصعبة في المعالجة بسبب غنى الصرف وكثرة اشتقاق الكلمات.",
    ]),
]


EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def make_pdf(sections, path, rtl=False):
    """Write HTML (one section per page) and print it to PDF with headless Edge,
    which embeds correct Unicode text for Arabic and Cyrillic."""
    lang = "ar" if rtl else "en"
    html = (f"<html lang='{lang}' dir='{'rtl' if rtl else 'ltr'}'><head><meta charset='utf-8'><style>"
            "body{font-family:'Segoe UI',Arial,sans-serif;font-size:13pt;line-height:1.6;margin:2cm}"
            "section{page-break-after:always}</style></head><body>"
            + "".join(f"<section><h1>{t}</h1>" + "".join(f"<p>{p}</p>" for p in ps) + "</section>"
                      for t, ps in sections) + "</body></html>")
    tmp = path.with_suffix(".html")
    tmp.write_text(html, encoding="utf-8")
    subprocess.run([str(EDGE), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={path}", tmp.as_uri()], check=True, capture_output=True)
    tmp.unlink()


def make_docx(sections, path):
    d = Document()
    for title, paras in sections:
        d.add_heading(title, level=1)
        for p in paras:
            d.add_paragraph(p)
    d.save(path)


make_pdf(EN, HERE / "solar_energy_en.pdf")
make_pdf(RU, HERE / "moscow_metro_ru.pdf")
make_pdf(AR, HERE / "ai_ar.pdf", rtl=True)
make_docx(AR, HERE / "ai_ar.docx")
print("done")
