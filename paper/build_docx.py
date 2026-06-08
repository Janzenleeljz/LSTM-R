"""生成符合《科学技术与工程》投稿模板的论文 Word 文件。

排版要点（依据期刊模板）：
- 页面 A4，页边距上下左右各 2 cm；
- 中英文标题、作者、单位、摘要、关键词通栏（单栏），正文双栏；
- 中文标题 黑体，作者 楷体，单位/摘要/关键词 宋体小号；英文标题/摘要对应；
- 节题三级编号（1 / 1.1 / 1.1.1），引言不编号、不加标题；
- 图表按正文提及顺序编号，图题/表题中英文对照；表为三线表；
- 量与单位以"量名称 /单位"标注，复合单位写作 (m·s-1) 形式；
- 变量用斜体，公式居中、编号右对齐；
- 参考文献顺序编码制，中文文献附英文译文。

运行：python paper/build_docx.py  ->  paper/危险货物运输车辆驾驶风险识别与分级方法.docx
"""
from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "results" / "figures"
TAB = ROOT / "results" / "tables"
OUT = ROOT / "paper" / "危险货物运输车辆驾驶风险识别与分级方法.docx"

# ---- 字体与字号 ----
SONG = "宋体"
HEI = "黑体"
KAI = "楷体"
TNR = "Times New Roman"

SZ_TITLE = 20      # 中文标题
SZ_AUTHOR = 14     # 中文作者
SZ_AFFIL = 9       # 单位
SZ_ABS = 9         # 摘要/关键词
SZ_ENTITLE = 16    # 英文标题
SZ_ENAUTHOR = 12   # 英文作者
SZ_BODY = 10       # 正文
SZ_H1 = 12         # 一级标题
SZ_H2 = 10.5       # 二级标题
SZ_CAP = 9         # 图题/表题/表格
SZ_EQ = 10.5       # 公式


def set_run_font(run, ascii_font=TNR, cjk_font=SONG, size=None, bold=None, italic=None):
    run.font.name = ascii_font
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), ascii_font)
    rfonts.set(qn("w:hAnsi"), ascii_font)
    rfonts.set(qn("w:eastAsia"), cjk_font)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic


def add_par(doc_or_par, align=None, space_after=2, space_before=0, line=None, first_indent=None):
    p = doc_or_par.add_paragraph()
    pf = p.paragraph_format
    if align is not None:
        p.alignment = align
    pf.space_after = Pt(space_after)
    pf.space_before = Pt(space_before)
    if line is not None:
        pf.line_spacing = line
    if first_indent is not None:
        pf.first_line_indent = first_indent
    return p


def add_runs(p, segments):
    """segments: list of (text, kwargs) for set_run_font; supports superscript via kw 'sup'."""
    for text, kw in segments:
        sup = kw.pop("sup", False)
        sub = kw.pop("sub", False)
        r = p.add_run(text)
        set_run_font(r, **kw)
        if sup:
            r.font.superscript = True
        if sub:
            r.font.subscript = True
    return p


def set_columns(section, num, space_cm=0.7):
    sectPr = section._sectPr
    cols = sectPr.find(qn("w:cols"))
    if cols is None:
        cols = OxmlElement("w:cols")
        sectPr.append(cols)
    cols.set(qn("w:num"), str(num))
    cols.set(qn("w:space"), str(int(space_cm * 567)))


def _no_space(p):
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.space_before = Pt(0)


# ---------- 正文构件 ----------

def body_par(doc, text, indent=True, size=SZ_BODY):
    p = add_par(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=3, line=1.15,
                first_indent=Pt(size * 2) if indent else None)
    r = p.add_run(text)
    set_run_font(r, cjk_font=SONG, size=size)
    return p


def body_rich(doc, segments, indent=True, size=SZ_BODY):
    p = add_par(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=3, line=1.15,
                first_indent=Pt(size * 2) if indent else None)
    add_runs(p, segments)
    return p


def h1(doc, text):
    p = add_par(doc, space_before=6, space_after=3)
    r = p.add_run(text)
    set_run_font(r, ascii_font=HEI, cjk_font=HEI, size=SZ_H1, bold=True)
    return p


def h2(doc, text):
    p = add_par(doc, space_before=4, space_after=2)
    r = p.add_run(text)
    set_run_font(r, ascii_font=HEI, cjk_font=HEI, size=SZ_H2, bold=True)
    return p


def full_width_block(doc):
    """切换到单栏（通栏），返回新建 section；调用方添加内容后再调用 back_to_two。"""
    sec = doc.add_section(WD_SECTION.CONTINUOUS)
    set_columns(sec, 1)
    return sec


def back_to_two(doc):
    sec = doc.add_section(WD_SECTION.CONTINUOUS)
    set_columns(sec, 2)
    return sec


def add_figure(doc, img, cn_cap, en_cap, width_cm=15.5, full_width=True):
    if full_width:
        full_width_block(doc)
    p = add_par(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=4, space_after=0)
    p.add_run().add_picture(str(img), width=Cm(width_cm))
    pc = add_par(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=1, space_after=0)
    r = pc.add_run(cn_cap)
    set_run_font(r, ascii_font=HEI, cjk_font=HEI, size=SZ_CAP)
    pe = add_par(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=4)
    r = pe.add_run(en_cap)
    set_run_font(r, ascii_font=TNR, cjk_font=SONG, size=SZ_CAP)
    if full_width:
        back_to_two(doc)


def _set_cell(cell, text, bold=False, align=WD_ALIGN_PARAGRAPH.CENTER, size=SZ_CAP):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = align
    _no_space(p)
    r = p.add_run(text)
    set_run_font(r, cjk_font=SONG, size=size, bold=bold)


def _three_line(table):
    """设置三线表：仅顶线、表头下线、底线，去除其余边框。"""
    tbl = table._tbl
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        if edge in ("top", "bottom"):
            el.set(qn("w:val"), "single"); el.set(qn("w:sz"), "8")
        else:
            el.set(qn("w:val"), "none"); el.set(qn("w:sz"), "0")
        el.set(qn("w:space"), "0"); el.set(qn("w:color"), "000000")
        borders.append(el)
    tblPr = tbl.tblPr
    tblPr.append(borders)
    # 表头行下加一条线
    hdr = table.rows[0]
    for cell in hdr.cells:
        tcPr = cell._tc.get_or_add_tcPr()
        tcb = OxmlElement("w:tcBorders")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single"); bottom.set(qn("w:sz"), "8")
        bottom.set(qn("w:space"), "0"); bottom.set(qn("w:color"), "000000")
        tcb.append(bottom)
        tcPr.append(tcb)


def add_table(doc, cn_cap, en_cap, header, rows, full_width=True, widths=None, size=SZ_CAP):
    if full_width:
        full_width_block(doc)
    pc = add_par(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=4, space_after=0)
    r = pc.add_run(cn_cap)
    set_run_font(r, ascii_font=HEI, cjk_font=HEI, size=SZ_CAP)
    pe = add_par(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=2)
    r = pe.add_run(en_cap)
    set_run_font(r, ascii_font=TNR, cjk_font=SONG, size=SZ_CAP)

    table = doc.add_table(rows=1, cols=len(header))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, htext in enumerate(header):
        _set_cell(table.rows[0].cells[j], htext, bold=True, size=size)
    for row in rows:
        cells = table.add_row().cells
        for j, val in enumerate(row):
            _set_cell(cells[j], val, align=WD_ALIGN_PARAGRAPH.CENTER, size=size)
    if widths:
        for j, w in enumerate(widths):
            for row in table.rows:
                row.cells[j].width = Cm(w)
    _three_line(table)
    if full_width:
        back_to_two(doc)
    return table


def eq(doc, latexish, number):
    """以居中段落呈现公式（变量斜体），右侧编号。供应录用时建议以 MathType 重排。"""
    p = add_par(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=3, space_after=3)
    r = p.add_run(latexish)
    set_run_font(r, ascii_font=TNR, cjk_font=SONG, size=SZ_EQ, italic=True)
    r2 = p.add_run("\t（" + number + "）")
    set_run_font(r2, ascii_font=TNR, cjk_font=SONG, size=SZ_EQ)
    # 右对齐编号的制表位
    from docx.enum.text import WD_TAB_ALIGNMENT
    p.paragraph_format.tab_stops.add_tab_stop(Cm(7.5), WD_TAB_ALIGNMENT.RIGHT)
    return p


# ---------- 读取真实结果，组装数据 ----------

def load_results():
    summ = json.loads((TAB / "run_summary.json").read_text(encoding="utf-8"))
    return summ


CN = {
    "overspeed_ratio": "超速占比",
    "overspeed_intensity": "超速强度",
    "hard_brake_rate": "急减速率",
    "hard_accel_rate": "急加速率",
    "speed_std": "速度标准差",
    "speed_entropy": "速度熵",
    "acc_rms": "加速度均方根",
    "continuous_over4h_ratio": "连续驾驶超4 h占比",
    "night_ratio": "夜间行驶占比",
    "bridge_tunnel_exposure": "桥隧接近暴露",
    "city_exposure": "城市中心暴露",
    "density_exposure": "建成区高密度暴露",
}


def fmt_p(p):
    return f"<0.001" if p < 1e-3 else f"{p:.3g}"


def build():
    summ = load_results()
    import csv

    weights = list(csv.DictReader((TAB / "indicator_weights.csv").open(encoding="utf-8-sig")))
    valid = list(csv.DictReader((TAB / "validation_consistency.csv").open(encoding="utf-8-sig")))

    doc = Document()
    # 页面与页边距
    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.top_margin = Cm(2.0)
    sec.bottom_margin = Cm(2.0)
    sec.left_margin = Cm(2.0)
    sec.right_margin = Cm(2.0)
    set_columns(sec, 1)
    # 默认样式字体
    style = doc.styles["Normal"]
    style.font.name = TNR
    style.font.size = Pt(SZ_BODY)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), SONG)

    # ===== 通栏题名区 =====
    p = add_par(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=4)
    r = p.add_run("基于北斗短报文定位数据的危险货物运输车辆驾驶风险识别与分级方法")
    set_run_font(r, ascii_font=HEI, cjk_font=HEI, size=SZ_TITLE, bold=True)

    p = add_par(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    add_runs(p, [
        ("作者一", dict(cjk_font=KAI, size=SZ_AUTHOR)),
        ("1", dict(cjk_font=KAI, size=SZ_AUTHOR, sup=True)),
        ("，作者二", dict(cjk_font=KAI, size=SZ_AUTHOR)),
        ("1, 2", dict(cjk_font=KAI, size=SZ_AUTHOR, sup=True)),
        ("*", dict(ascii_font=TNR, cjk_font=KAI, size=SZ_AUTHOR, sup=True)),
        ("，作者三", dict(cjk_font=KAI, size=SZ_AUTHOR)),
        ("2", dict(cjk_font=KAI, size=SZ_AUTHOR, sup=True)),
    ])

    p = add_par(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6)
    r = p.add_run("（1. 单位一，城市 邮编；2. 单位二，城市 邮编）")
    set_run_font(r, cjk_font=SONG, size=SZ_AFFIL)

    # 摘要
    abs_cn = ("针对危险货物运输车辆（简称危货车）安全监管中事故与违章标签稀缺、北斗短报文（RDSS）"
              "定位数据稀疏且采样间隔不等的难题，提出一种融合多维替代安全指标与自监督轨迹表征的危货车"
              "驾驶风险识别与分级方法。首先，面向北斗短报文低频、不等间隔的采样特征，设计稀疏对齐与"
              "固定步长重采样流程，生成插值掩码并依据长盲区与持续停车切分驾驶段；其次，构建涵盖驾驶"
              "行为、监管合规与情境暴露三个维度、共12项方向统一的替代安全指标，以熵权法与CRITIC法的"
              "几何平均进行组合赋权；再次，提出一种采样间隔感知、带掩码重构的长短期记忆（LSTM）自编码器，"
              "在无标签驾驶段序列上自监督地学习轨迹表征，以重构误差作为异常分量；最后，用逼近理想解排序法"
              "（TOPSIS）将加权指标分量与自监督异常分量融合为综合运行风险指数，并以一维K均值聚类实现"
              "四级风险划分。基于某区域25辆危货车2024年1月的1 048 575条真实北斗定位记录开展实验，"
              "预处理得到1 441 032个重采样网格点与2 688个有效驾驶段。结果表明：综合风险指数在指数空间的"
              "聚类轮廓系数为0.572；12项替代安全指标在四个风险等级间的差异均通过Kruskal-Wallis检验"
              "（p<0.001），其中10项随等级严格单调递增；消融实验中综合指数与仅指标、仅自监督两个变体的"
              "Spearman相关分别为0.708与0.777，表明两类信息对最终风险排序均有实质贡献。所提方法不依赖"
              "事故标签，可对驾驶风险倾向进行量化与分级，为危货运输差异化监管提供技术支撑。")
    p = add_par(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=2)
    add_runs(p, [("摘要  ", dict(cjk_font=HEI, size=SZ_ABS, bold=True)),
                 (abs_cn, dict(cjk_font=SONG, size=SZ_ABS))])

    p = add_par(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=2)
    add_runs(p, [("关键词  ", dict(cjk_font=HEI, size=SZ_ABS, bold=True)),
                 ("北斗短报文；危险货物运输；驾驶风险识别；风险分级；自监督学习；TOPSIS",
                  dict(cjk_font=SONG, size=SZ_ABS))])

    p = add_par(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=6)
    add_runs(p, [("中图法分类号  ", dict(cjk_font=HEI, size=SZ_ABS, bold=True)),
                 ("U492.8；TP391    ", dict(ascii_font=TNR, cjk_font=SONG, size=SZ_ABS)),
                 ("文献标志码  ", dict(cjk_font=HEI, size=SZ_ABS, bold=True)),
                 ("A", dict(ascii_font=TNR, cjk_font=SONG, size=SZ_ABS))])

    # 英文题名区
    p = add_par(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=2, space_after=3)
    r = p.add_run("Driving-risk Identification and Grading Method for Hazardous-materials "
                  "Transport Vehicles Based on BeiDou Short-message Positioning Data")
    set_run_font(r, ascii_font=TNR, cjk_font=TNR, size=SZ_ENTITLE, bold=True)

    p = add_par(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    add_runs(p, [("AUTHOR Yi", dict(ascii_font=TNR, size=SZ_ENAUTHOR)),
                 ("1", dict(ascii_font=TNR, size=SZ_ENAUTHOR, sup=True)),
                 (", AUTHOR Er", dict(ascii_font=TNR, size=SZ_ENAUTHOR)),
                 ("1, 2", dict(ascii_font=TNR, size=SZ_ENAUTHOR, sup=True)),
                 ("*", dict(ascii_font=TNR, size=SZ_ENAUTHOR, sup=True)),
                 (", AUTHOR San", dict(ascii_font=TNR, size=SZ_ENAUTHOR)),
                 ("2", dict(ascii_font=TNR, size=SZ_ENAUTHOR, sup=True))])

    p = add_par(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6)
    r = p.add_run("(1. Affiliation One, City Postcode, China; 2. Affiliation Two, City Postcode, China)")
    set_run_font(r, ascii_font=TNR, size=SZ_AFFIL)

    abs_en = ("To address the scarcity of accident/violation labels and the sparse, irregularly "
              "sampled nature of BeiDou short-message (RDSS) positioning data in the safety supervision "
              "of hazardous-materials (hazmat) transport vehicles, a driving-risk identification and "
              "grading method that fuses multi-dimensional surrogate safety indicators with "
              "self-supervised trajectory representations is proposed. A sparse-alignment and fixed-step "
              "resampling procedure is designed for the low-frequency, irregular sampling, producing "
              "interpolation masks and segmenting driving sessions by long blind gaps and sustained stops. "
              "A 12-indicator surrogate safety system spanning driving behavior, regulatory compliance and "
              "contextual exposure is constructed, with weights obtained by a geometric-mean combination of "
              "the entropy-weight and CRITIC methods. A sampling-interval-aware LSTM autoencoder with masked "
              "reconstruction learns trajectory representations self-supervised from unlabeled driving-session "
              "sequences, and its reconstruction error serves as an anomaly component. Finally, TOPSIS fuses "
              "the weighted indicator component and the anomaly component into a composite operating-risk index, "
              "and one-dimensional K-means clustering yields a four-level grading. Experiments on 1 048 575 real "
              "BeiDou records from 25 hazmat vehicles (January 2024) yield 1 441 032 resampled grid points and "
              "2 688 valid driving sessions. The index attains a clustering silhouette of 0.572 in index space; "
              "all 12 indicators differ significantly across the four grades (Kruskal-Wallis, p<0.001), and 10 of "
              "them increase strictly monotonically with grade. Ablation shows Spearman correlations of 0.708 and "
              "0.777 between the composite index and the indicator-only / anomaly-only variants, confirming that "
              "both components contribute substantively. The method requires no accident labels and quantifies and "
              "grades driving-risk propensity, providing technical support for differentiated supervision of hazmat "
              "transport.")
    p = add_par(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=2)
    add_runs(p, [("[Abstract]  ", dict(ascii_font=TNR, size=SZ_ABS, bold=True)),
                 (abs_en, dict(ascii_font=TNR, size=SZ_ABS))])

    p = add_par(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=4)
    add_runs(p, [("[Keywords]  ", dict(ascii_font=TNR, size=SZ_ABS, bold=True)),
                 ("BeiDou short message; hazardous-materials transport; driving-risk identification; "
                  "risk grading; self-supervised learning; TOPSIS", dict(ascii_font=TNR, size=SZ_ABS))])

    # ===== 切换为双栏正文 =====
    body_sec = doc.add_section(WD_SECTION.CONTINUOUS)
    set_columns(body_sec, 2)

    build_body(doc, summ, weights, valid)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT))
    print("saved", OUT)


def build_body(doc, summ, weights, valid):
    v = summ["validation"]
    gc = v["grade_counts"]
    vmap = {row["indicator"]: row for row in valid}
    wmap = {row["indicator"]: row for row in weights}

    # ---------------- 引言（不编号） ----------------
    body_par(doc,
        "危险货物运输事关公共安全，一旦发生事故往往造成重大人员伤亡、财产损失与环境污染，因而是道路"
        "运输安全监管的重点对象。我国对危货车实施卫星定位强制入网监管，其中北斗短报文（RDSS）凭借"
        "在公网覆盖薄弱区域的通信能力，成为偏远路段与跨区域长途运输的重要定位回传手段。然而，受短报文"
        "通信带宽与计费机制约束，北斗短报文定位数据呈现采样频率低、采样间隔不等、长时间盲区频发的特征，"
        "与车载OBD/CAN等高频数据存在本质差异，给基于轨迹的驾驶风险分析带来困难。")
    body_par(doc,
        "在驾驶风险量化方面，既有研究多基于高频车载数据（CAN/OBD、惯性测量单元、视频）提取急加速、"
        "急减速、急转弯等事件并构建风险评分，此类方法依赖高采样率与丰富传感通道，难以直接迁移至带宽受限、"
        "低频回传的北斗短报文场景。在危货运输安全方面，已有工作多在路网或地理信息层面进行宏观风险评估"
        "，如基于区间层次分析与集对分析的危货道路运输风险评估[1]、面向城市道路的事故概率与后果综合评价[2]，"
        "较少在个体车辆—驾驶段尺度上结合实际运行轨迹刻画驾驶风险。在综合评价方法方面，熵权法、CRITIC法、"
        "逼近理想解排序法（TOPSIS）等被广泛用于交通安全多指标评价，如基于熵权-TOPSIS的道路货运企业"
        "运营安全评估[3]与大宗货物运输方式综合评价[4]，但多以静态统计指标为输入，鲜有与轨迹表征学习相结合。"
        "在稀疏/不等间隔时间序列建模方面，时间间隔嵌入、掩码重构、面向缺失值的循环网络[5]等方法为处理"
        "不规则采样提供了思路，基于长短期记忆网络的自编码器[6-7]亦被用于无监督异常检测。")
    body_par(doc,
        "综合来看，危货运输安全监管长期面临标签稀缺问题：事故为小概率事件，违章记录零散且难以与轨迹"
        "精确对齐，导致以事故预测为目标的监督学习范式难以落地。如何在无事故标签、稀疏不等间隔的北斗短报文"
        "数据上，对驾驶风险倾向进行可靠的量化与分级，仍是亟待解决的问题。为此，本文不以直接预测事故概率"
        "为目标，而从风险识别、风险倾向量化与风险等级划分的角度，提出一套面向北斗短报文数据特征的完整方法："
        "①设计稀疏对齐—固定步长重采样—插值掩码—驾驶段切分的预处理范式，并显式保留采样稀疏性信息；"
        "②构建驾驶行为、监管合规、情境暴露三维共12项方向统一的替代安全指标，并以熵权-CRITIC几何平均"
        "组合赋权；③提出采样间隔感知、带掩码重构的LSTM自编码器，以重构误差刻画偏离常态的异常驾驶模式；"
        "④用TOPSIS融合加权指标分量与自监督异常分量得到综合运行风险指数并实现四级分级，最后从内部聚类质量、"
        "外部指标一致性、消融三方面进行系统验证。基于25辆危货车一个月真实数据的实验，期望验证所提方法在"
        "无标签条件下识别与分级驾驶风险的有效性与可解释性。")

    # ---------------- 1 数据与问题描述 ----------------
    h1(doc, "1  数据与问题描述")
    h2(doc, "1.1  数据来源与特征")
    body_par(doc,
        "实验数据为某区域25辆危货车2024年1月1日至28日的北斗短报文定位记录，共1 048 575条。每条记录"
        "包含车牌标识、瞬时速度、经度、纬度、累计里程与定位时刻。车辆活动空间以苏皖沿江地区"
        "（南京—扬州—镇江—常州—无锡—苏州一带）为主，并含跨省长途运输。")
    body_par(doc,
        "数据呈现典型北斗短报文特征：速度被监管限速封顶于0~85 km/h，均值约28.3 km/h，中位数约11 km/h，"
        "速度为零（停车或装卸）的记录约占48.7 %；相邻报文采样间隔中位数约30 s，90 %分位约120 s，99 %分位"
        "约300 s，并存在长达数十小时的长盲区。如图1所示，采样间隔分布高度集中于若干离散档位（约30、120、"
        "300 s），直观反映其低频、不等间隔与稀疏特征。")
    add_figure(doc, FIG / "fig_sparsity.png",
               "图1  北斗短报文采样间隔分布", "Fig.1  Distribution of BeiDou short-message sampling intervals",
               width_cm=10.5)

    h2(doc, "1.2  问题定义")
    body_rich(doc, [
        ("记车辆集合为 ", dict(cjk_font=SONG, size=SZ_BODY)),
        ("V", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        (" ={ ", dict(ascii_font=TNR, size=SZ_BODY)),
        ("v", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        ("1", dict(ascii_font=TNR, size=SZ_BODY, sub=True)),
        (", …, ", dict(ascii_font=TNR, size=SZ_BODY)),
        ("v", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        ("25", dict(ascii_font=TNR, size=SZ_BODY, sub=True)),
        (" }。对车辆 ", dict(cjk_font=SONG, size=SZ_BODY)),
        ("v", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        ("，其原始报文序列为 {(", dict(cjk_font=SONG, size=SZ_BODY)),
        ("t", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        ("i", dict(ascii_font=TNR, size=SZ_BODY, italic=True, sub=True)),
        (", ", dict(ascii_font=TNR, size=SZ_BODY)),
        ("p", dict(ascii_font=TNR, size=SZ_BODY, italic=True, bold=True)),
        ("i", dict(ascii_font=TNR, size=SZ_BODY, italic=True, sub=True)),
        (", ", dict(ascii_font=TNR, size=SZ_BODY)),
        ("s", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        ("i", dict(ascii_font=TNR, size=SZ_BODY, italic=True, sub=True)),
        (", ", dict(ascii_font=TNR, size=SZ_BODY)),
        ("m", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        ("i", dict(ascii_font=TNR, size=SZ_BODY, italic=True, sub=True)),
        (")}，其中 ", dict(cjk_font=SONG, size=SZ_BODY)),
        ("t", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        ("i", dict(ascii_font=TNR, size=SZ_BODY, italic=True, sub=True)),
        (" 为时刻、", dict(cjk_font=SONG, size=SZ_BODY)),
        ("p", dict(ascii_font=TNR, size=SZ_BODY, italic=True, bold=True)),
        ("i", dict(ascii_font=TNR, size=SZ_BODY, italic=True, sub=True)),
        (" 为位置、", dict(cjk_font=SONG, size=SZ_BODY)),
        ("s", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        ("i", dict(ascii_font=TNR, size=SZ_BODY, italic=True, sub=True)),
        (" 为速度、", dict(cjk_font=SONG, size=SZ_BODY)),
        ("m", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        ("i", dict(ascii_font=TNR, size=SZ_BODY, italic=True, sub=True)),
        (" 为里程；采样间隔 Δ", dict(cjk_font=SONG, size=SZ_BODY)),
        ("t", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        ("i", dict(ascii_font=TNR, size=SZ_BODY, italic=True, sub=True)),
        (" =", dict(ascii_font=TNR, size=SZ_BODY)),
        ("t", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        ("i", dict(ascii_font=TNR, size=SZ_BODY, italic=True, sub=True)),
        (" −", dict(ascii_font=TNR, size=SZ_BODY)),
        ("t", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        ("i", dict(ascii_font=TNR, size=SZ_BODY, italic=True, sub=True)),
        ("−1", dict(ascii_font=TNR, size=SZ_BODY, sub=True)),
        (" 非定值。由于缺乏事故/违章标签，本文目标并非学习事故发生概率，而是：①风险识别，"
         "识别偏离常态、具有更高风险倾向的驾驶段；②风险量化，为每个驾驶段计算可比较的综合运行风险指数 ",
         dict(cjk_font=SONG, size=SZ_BODY)),
        ("R", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        (" ∈[0, 1]；③风险分级，将驾驶段与车辆划分为有序风险等级，并验证其与替代安全指标的一致性。",
         dict(cjk_font=SONG, size=SZ_BODY)),
    ])

    # ---------------- 2 方法 ----------------
    h1(doc, "2  危货车驾驶风险识别与分级方法")
    body_par(doc,
        "所提方法包含五个环节：数据清洗与质量控制、稀疏对齐与重采样、驾驶段切分（2.2~2.4）；多维替代"
        "安全指标体系与组合赋权（2.5~2.6）；采样间隔感知的自监督轨迹表征（2.7）；TOPSIS综合运行风险指数"
        "（2.8）；风险分级与验证（2.9）。")

    h2(doc, "2.1  数据清洗与质量控制")
    body_par(doc,
        "统一字段与编码（原始为GBK），解析日期与定位时刻合成时间戳；剔除位置越界（经度73°~135°、纬度"
        "3°~54°之外）、速度越界（小于0或大于100 km/h）及关键字段缺失的记录；对同一车辆同一时刻去重，"
        "并按车辆—时间排序。进一步剔除相邻点位移异常跳变（位移大于5 km且等效时速大于150 km/h）以抑制"
        "定位野值。", indent=True)

    h2(doc, "2.2  稀疏对齐与重采样")
    body_rich(doc, [
        ("为消除采样间隔不等的影响，对每辆车按长盲区阈值 ", dict(cjk_font=SONG, size=SZ_BODY)),
        ("τ", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        ("g", dict(ascii_font=TNR, size=SZ_BODY, italic=True, sub=True)),
        (" =600 s 将序列切分为若干连续段；段内以固定步长 Δ=30 s 重采样，对经度、纬度、速度、里程做"
         "线性插值，得到等步长网格序列。同时生成两类稀疏性信息：插值掩码 mask", dict(cjk_font=SONG, size=SZ_BODY)),
        ("k", dict(ascii_font=TNR, size=SZ_BODY, italic=True, sub=True)),
        (" ∈{0, 1} 表示网格点 ", dict(ascii_font=TNR, size=SZ_BODY)),
        ("k", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        (" 的 ±Δ/2 邻域内是否存在原始观测；局部采样间隔 gap", dict(cjk_font=SONG, size=SZ_BODY)),
        ("k", dict(ascii_font=TNR, size=SZ_BODY, italic=True, sub=True)),
        (" 刻画该点所处的原始采样间隔。长盲区不进行跨段插值，从而避免在无观测区间制造虚假轨迹。",
         dict(cjk_font=SONG, size=SZ_BODY)),
    ])

    h2(doc, "2.3  驾驶段切分")
    body_par(doc,
        "危货运输管理要求连续驾驶不超过4 h、之后须休息不少于20 min。据此，将持续停车（速度小于2 km/h）"
        "时长不小于20 min视为一次合规休息，并以此切分驾驶段（两次合规休息之间的连续驾驶）；短时停车"
        "（如等灯、短暂装卸）并入相邻驾驶段。过滤时长不足5 min或里程不足1 km的无效段。该定义使驾驶段与"
        "监管连续驾驶单元对齐，便于直接评估连续驾驶合规性。经上述处理，25辆车共得到1 441 032个重采样"
        "网格点、2 688个有效驾驶段，覆盖总里程约1.85×10⁵ km。")

    h2(doc, "2.4  多维替代安全指标体系")
    body_par(doc,
        "在无事故标签条件下，以可观测、可解释、与安全相关为原则，构建三维共12项替代安全指标，方向"
        "统一为数值越大风险越高（表1）。其中，受北斗短报文30 s级采样限制，瞬时加减速度不可观测，故将"
        "急减速、急加速操作化为单个采样间隔内速度突变不小于15 km/h的可观测替代事件，且仅在密采样步"
        "（Δt不大于60 s）上计数，按每100 km归一，以避免跨长插值段产生伪事件。各指标先在驾驶段尺度"
        "计算，再以里程为权重聚合到车辆尺度。")
    add_table(doc, "表1  替代安全指标体系", "Table 1  Surrogate safety indicator system",
              ["维度", "指标", "定义与口径"],
              [
                  ["驾驶行为", "超速占比", "速度超过限速(80 km/h)的网格点占比"],
                  ["", "超速强度", "超速时段的平均超速量 /(km·h⁻¹)"],
                  ["", "急减速率", "速度突变≤−15 km/h的密采样事件数 /(100 km)⁻¹"],
                  ["", "急加速率", "速度突变≥+15 km/h的密采样事件数 /(100 km)⁻¹"],
                  ["", "速度标准差", "驾驶段速度的标准差 /(km·h⁻¹)"],
                  ["", "速度熵", "速度直方图分布的信息熵"],
                  ["", "加速度均方根", "等步长速度差分的均方根 /(m·s⁻²)"],
                  ["监管合规", "连续驾驶超4 h占比", "驾驶段超过4 h部分的时间占比"],
                  ["", "夜间行驶占比", "22:00—06:00时段网格点占比"],
                  ["情境暴露", "桥隧接近暴露", "位于已知跨江桥隧1 km缓冲内的网格点占比"],
                  ["", "城市中心暴露", "位于主要城市中心5 km缓冲内的网格点占比"],
                  ["", "建成区高密度暴露", "位于点密度高分位(≥90 %)网格的网格点占比"],
              ], widths=[1.8, 3.0, 9.5], full_width=True)

    h2(doc, "2.5  指标标准化与组合赋权")
    body_par(doc,
        "所有指标均为正向，采用极差(min-max)标准化至[0, 1]。为降低单一客观赋权的偏倚，结合两种互补"
        "方法：熵权法度量各指标的信息量(离散程度)，CRITIC法兼顾对比强度(标准差)与指标间冲突性(1−相关)。"
        "最终权重取二者几何平均后归一，如式(1)所示。", indent=True)
    eq(doc, "w_j = √(w_j^ent · w_j^cri) / Σ_l √(w_l^ent · w_l^cri)", "1")
    body_rich(doc, [
        ("式(1)中：", dict(cjk_font=SONG, size=SZ_BODY)),
        ("w", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        ("j", dict(ascii_font=TNR, size=SZ_BODY, italic=True, sub=True)),
        (" 为指标 ", dict(cjk_font=SONG, size=SZ_BODY)),
        ("j", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        (" 的组合权重；", dict(cjk_font=SONG, size=SZ_BODY)),
        ("w", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        ("j", dict(ascii_font=TNR, size=SZ_BODY, italic=True, sub=True)),
        ("ent", dict(ascii_font=TNR, size=SZ_BODY, sup=True)),
        ("、", dict(cjk_font=SONG, size=SZ_BODY)),
        ("w", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        ("j", dict(ascii_font=TNR, size=SZ_BODY, italic=True, sub=True)),
        ("cri", dict(ascii_font=TNR, size=SZ_BODY, sup=True)),
        (" 分别为熵权法与CRITIC法所得权重。所得组合权重见3.2节表2。", dict(cjk_font=SONG, size=SZ_BODY)),
    ])

    h2(doc, "2.6  采样间隔感知的掩码重构LSTM自编码器")
    body_par(doc,
        "为在无标签条件下刻画偏离常态的异常驾驶模式，在重采样驾驶段序列上训练LSTM自编码器。每个时间步"
        "特征为标准化的速度、加速度、加加速度、速度变化量以及采样间隔Δt；其中Δt作为显式特征输入，使模型"
        "感知局部采样稀疏程度(采样间隔感知)。以滑动窗口(长度32步、步长16步)切分得到28 989个样本窗口。"
        "编码器为单层LSTM，将窗口编码为16维潜变量；解码器由潜变量重建整个窗口序列。训练时对部分时间步"
        "随机置零(掩码比例15 %)以增强对稀疏/缺失的鲁棒性(掩码重构)，损失为重构均方误差。窗口重构误差"
        "越大，表示其轨迹模式越偏离群体常态，记为异常分量；将窗口误差按驾驶段聚合(取均值)得到驾驶段"
        "异常分量。如图2所示，验证集损失由0.747降至0.583并趋于平稳，表明模型有效学到了常态轨迹结构。")
    add_figure(doc, FIG / "fig_training_curve.png",
               "图2  自监督LSTM自编码器训练曲线",
               "Fig.2  Training curves of the self-supervised LSTM autoencoder", width_cm=10.5)

    h2(doc, "2.7  TOPSIS综合运行风险指数")
    body_rich(doc, [
        ("将12项加权替代安全指标与自监督异常分量统一为正向风险准则，构成决策矩阵，采用TOPSIS计算每个"
         "驾驶段相对最危险解与最安全解的相对贴近度作为综合运行风险指数，如式(2)所示。",
         dict(cjk_font=SONG, size=SZ_BODY)),
    ])
    eq(doc, "R_i = d_i⁻ / (d_i⁺ + d_i⁻)", "2")
    body_rich(doc, [
        ("式(2)中：", dict(cjk_font=SONG, size=SZ_BODY)),
        ("R", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        ("i", dict(ascii_font=TNR, size=SZ_BODY, italic=True, sub=True)),
        (" 为驾驶段 ", dict(cjk_font=SONG, size=SZ_BODY)),
        ("i", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        (" 的综合运行风险指数；", dict(cjk_font=SONG, size=SZ_BODY)),
        ("d", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        ("i", dict(ascii_font=TNR, size=SZ_BODY, italic=True, sub=True)),
        ("⁺", dict(ascii_font=TNR, size=SZ_BODY, sup=True)),
        ("、", dict(cjk_font=SONG, size=SZ_BODY)),
        ("d", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        ("i", dict(ascii_font=TNR, size=SZ_BODY, italic=True, sub=True)),
        ("⁻", dict(ascii_font=TNR, size=SZ_BODY, sup=True)),
        (" 分别为加权规范化后到最危险理想解、最安全理想解的欧氏距离。异常分量权重设为 ",
         dict(cjk_font=SONG, size=SZ_BODY)),
        ("α", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        (" =0.3，其余(1−", dict(ascii_font=TNR, size=SZ_BODY)),
        ("α", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        (")按组合权重分配给12项指标。", dict(cjk_font=SONG, size=SZ_BODY)),
        ("R", dict(ascii_font=TNR, size=SZ_BODY, italic=True)),
        (" 越大表示风险倾向越高。", dict(cjk_font=SONG, size=SZ_BODY)),
    ])

    h2(doc, "2.8  风险分级与验证方法")
    body_par(doc,
        "对综合风险指数分别采用分位法与一维K均值聚类进行四级划分(低风险/中风险/高风险/极高风险)，"
        "K均值簇按均值升序映射为有序等级。验证从三方面进行：①内部聚类质量，计算指数空间与指标空间的"
        "轮廓系数；②外部一致性，以Kruskal-Wallis检验各替代安全指标在等级间的差异显著性、考察其随等级的"
        "单调性，并计算指数与各指标的Spearman相关；③消融，比较综合指数与仅指标、仅自监督两个变体的"
        "相关性与分级一致性(调整兰德指数ARI)，以验证两类信息的互补贡献。")

    # ---------------- 3 实验结果 ----------------
    h1(doc, "3  实验结果与分析")
    h2(doc, "3.1  实验设置")
    body_par(doc,
        "实验在CPU环境下完成，编程语言为Python 3.12，主要依赖numpy、pandas、scikit-learn、scipy、"
        "matplotlib与PyTorch(CPU版)。自编码器训练25轮，按85∶15划分训练/验证集，优化器为Adam[8]，"
        "随机种子固定以保证可复现。全流程(含重采样、指标计算、表征训练、融合、分级与作图)在普通工作站"
        "约60 s内完成。")

    h2(doc, "3.2  指标权重")
    body_par(doc,
        "组合赋权结果见表2。可见夜间行驶占比、建成区高密度暴露、城市中心暴露等指标组合权重较高，"
        "符合危货运输安全的先验认知；熵权法对连续驾驶超4 h占比赋予较高权重(因其取值稀有、信息量大)，"
        "而CRITIC法对速度类波动指标赋权较高(因其离散度大)，几何平均组合在二者间取得平衡，避免单一"
        "方法的偏倚。")
    wt_rows = []
    for k in CN:
        r = wmap[k]
        wt_rows.append([CN[k], f"{float(r['w_entropy']):.3f}",
                        f"{float(r['w_critic']):.3f}", f"{float(r['w_combined']):.3f}"])
    add_table(doc, "表2  替代安全指标的组合权重",
              "Table 2  Combined weights of surrogate safety indicators",
              ["指标", "熵权法", "CRITIC法", "组合权重"], wt_rows,
              widths=[5.2, 2.6, 2.6, 2.6], full_width=True)

    h2(doc, "3.3  风险指数与分级分布")
    body_par(doc,
        "如图3所示，驾驶段综合运行风险指数整体右偏(均值0.062、中位数0.054、最大0.513)，绝大多数驾驶段"
        "处于中低风险区间，少数驾驶段具有显著更高的风险倾向，符合危货运输多数合规、少数高危的实际；"
        "K均值分级将指数划分为连续且互不重叠的四段。如图4所示，在2 688个驾驶段中，低/中/高/极高风险"
        f"分别为{gc['0']}、{gc['1']}、{gc['2']}、{gc['3']}个；在25辆车中分别为9、8、6、2辆。按第90 %"
        "分位阈值识别出269个高风险驾驶段，可作为监管重点核查对象。")
    add_figure(doc, FIG / "fig_risk_distribution.png",
               "图3  综合运行风险指数分布(左:整体;右:各风险等级)",
               "Fig.3  Distribution of the composite operating-risk index", width_cm=15.5)
    add_figure(doc, FIG / "fig_grade_counts.png",
               "图4  风险等级分布(左:驾驶段;右:车辆)",
               "Fig.4  Risk-grade distribution of driving sessions (left) and vehicles (right)",
               width_cm=15.5)

    h2(doc, "3.4  分级有效性验证")
    body_par(doc,
        "内部聚类质量方面，综合风险指数空间的聚类轮廓系数为0.572，表明四级划分在指数维度上分离良好；"
        "指标空间轮廓系数仅0.047，反映原始12维指标空间高度重叠、单指标难以直接分级，从而凸显综合指数"
        "的必要性。")
    body_par(doc,
        "外部一致性方面，如表3与图5所示，全部12项替代安全指标在四个风险等级间的差异均通过Kruskal-Wallis"
        "检验(p<0.001)，其中10项随等级严格单调递增；指数与加速度均方根、速度熵、急加速率等行为指标的"
        "Spearman相关较强(加速度均方根达0.730)。这表明风险等级越高的驾驶段，确实表现出更剧烈的速度波动、"
        "更频繁的速度突变与更高的暴露占比，分级结果具有良好的构念效度。需要指出的是，连续驾驶超4 h占比与"
        "夜间行驶占比两项未呈严格单调：前者因合规性总体良好(2 688个驾驶段中仅3个触发连续驾驶超4 h)、"
        "取值高度稀疏，故其Spearman相关较弱(0.038)但组间差异仍显著；后者在高风险等级出现峰值而在极高风险"
        "等级回落，反映极高风险更多由速度突变与建成区暴露主导，而非夜间因素，符合多因素耦合的实际。")
    val_rows = []
    show = ["acc_rms", "hard_accel_rate", "hard_brake_rate", "speed_entropy", "speed_std",
            "night_ratio", "density_exposure", "overspeed_intensity", "continuous_over4h_ratio"]
    for k in show:
        r = vmap[k]
        def f(x):
            x = float(x)
            return f"{x:.3g}"
        val_rows.append([CN[k], f(r["mean_L0"]), f(r["mean_L1"]), f(r["mean_L2"]), f(r["mean_L3"]),
                         f"{float(r['spearman_rho']):.3f}", fmt_p(float(r["kruskal_p"]))])
    add_table(doc, "表3  各风险等级的指标均值与一致性检验",
              "Table 3  Indicator means by risk grade and consistency tests",
              ["指标", "低风险", "中风险", "高风险", "极高风险", "Spearman ρ", "Kruskal p"],
              val_rows, widths=[3.6, 1.7, 1.7, 1.7, 1.9, 1.9, 1.7], full_width=True)
    add_figure(doc, FIG / "fig_validation.png",
               "图5  分级外部一致性(左:指标均值行归一化热力图;右:代表性指标)",
               "Fig.5  External consistency of the risk grading", width_cm=15.5)

    h2(doc, "3.5  消融分析")
    body_par(doc,
        "为验证加权指标与自监督异常两类信息的互补性，比较综合指数与两个变体的关系：综合指数与仅指标"
        "变体的Spearman相关为0.708、分级ARI为0.158；与仅自监督变体的Spearman相关为0.777、分级ARI为0.328。"
        "结果表明，两类信息均与最终风险排序高度相关，但任一单独分量都无法完全决定综合分级(ARI显著小于1)，"
        "说明TOPSIS融合确实整合了规则化指标与数据驱动异常两方面的互补信息，自监督异常分量的引入对最终"
        "分级产生了实质性的、不可被指标完全替代的影响。此外，分位法与K均值两种分级方案高度一致"
        "(Spearman 0.917、ARI 0.510)，说明分级结果对划分方法不敏感，具有稳健性。")

    h2(doc, "3.6  指标相关性与空间分布")
    body_par(doc,
        "如图6所示，急加速率与急减速率、速度标准差与加速度均方根等存在中等正相关，而暴露类指标与行为类"
        "指标相关较弱、信息互补，支持采用CRITIC等考虑冲突性的赋权方法。如图7所示，核心研究区(苏皖沿江)"
        "轨迹点的风险等级空间分布显示，高风险点主要集中于城市建成区与若干主干通道交汇处，低风险点多见于"
        "高速公路与城郊路段，与建成区高密度暴露、城市中心暴露等指标的空间含义一致。")
    add_figure(doc, FIG / "fig_indicator_corr.png",
               "图6  替代安全指标相关性矩阵",
               "Fig.6  Correlation matrix of surrogate safety indicators", width_cm=11.0)
    add_figure(doc, FIG / "fig_spatial_risk.png",
               "图7  核心研究区轨迹点风险等级空间分布",
               "Fig.7  Spatial distribution of risk grades in the core study area", width_cm=11.0)

    # ---------------- 4 讨论 ----------------
    h1(doc, "4  讨论")
    body_par(doc,
        "在方法学层面，本文将风险操作化为可观测的替代安全指标与数据驱动的轨迹异常，规避了危货运输事故"
        "标签稀缺导致的监督学习困境；通过显式采样间隔建模与掩码重构，使表征学习适配北斗短报文的稀疏"
        "不等间隔特征。在应用层面，综合运行风险指数与四级分级可直接服务于差异化监管：对极高/高风险车辆"
        "(如本实验识别出的2辆极高风险车)实施重点监控与约谈，对高风险驾驶段(如速度突变频繁、穿越建成区、"
        "连续驾驶时长偏长的行程)进行预警与核查，从而将有限监管资源投向高风险对象。")
    body_par(doc,
        "本文方法仍存在局限：①情境暴露依赖敏感目标图层，在缺乏权威POI/GIS数据时采用研究区已知跨江桥隧、"
        "主要城市中心与数据驱动点密度作为近似代理，可能低估或错配部分敏感目标暴露，后续应接入权威危货专用"
        "敏感目标(隧道、桥梁、学校、医院、水源地、人口密集区)图层；②30 s级采样无法观测真正的瞬时急加减速，"
        "本文以采样间隔内速度突变作为可观测替代，未来可结合具备高频段的混合数据源进行校验；③本文为"
        "无监督/自监督范式，缺乏事故金标准外部验证，后续可在获得稀疏事故/违章记录后开展半监督校验与阈值"
        "标定；④样本为25辆车一个月数据，规模有限，结论的普适性有待在更大规模、跨区域数据上检验。")

    # ---------------- 5 结论 ----------------
    h1(doc, "5  结论")
    body_par(doc,
        "面向北斗短报文定位数据稀疏、不等间隔与事故标签稀缺的现实约束，提出并实现了一套危货车驾驶风险"
        "识别与分级方法，得到以下结论。", indent=True)
    for t in [
        "(1) 所设计的稀疏对齐—固定步长重采样—驾驶段切分预处理范式，可将不规则北斗短报文转化为可分析的"
        "等步长驾驶段序列，并显式保留采样稀疏性信息；三维12项替代安全指标与熵权-CRITIC组合赋权，在无"
        "事故标签条件下提供了可解释的风险刻画。",
        "(2) 采样间隔感知、带掩码重构的LSTM自编码器可在无标签驾驶段上自监督地提取轨迹异常；经TOPSIS"
        "融合得到的综合运行风险指数在指数空间聚类轮廓系数达0.572，四级分级分离良好。",
        "(3) 分级有效性得到系统验证：12项替代安全指标在各等级间差异均显著(p<0.001)，其中10项随等级严格"
        "单调递增；消融分析表明加权指标与自监督异常两类信息对最终风险排序均有实质且互补的贡献，分级结果"
        "对划分方法不敏感(分位法与K均值ARI为0.510)。",
        "(4) 所提方法可复现、可解释、可落地，为危货运输的差异化、精准化安全监管提供了有效的技术途径；"
        "后续将接入权威敏感目标图层、引入稀疏事故标签进行半监督校验，并在更大规模数据上检验普适性。",
    ]:
        p = add_par(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=3, line=1.15,
                    first_indent=Pt(SZ_BODY * 2))
        r = p.add_run(t)
        set_run_font(r, cjk_font=SONG, size=SZ_BODY)

    # ---------------- 参考文献 ----------------
    p = add_par(doc, space_before=6, space_after=3)
    r = p.add_run("参考文献")
    set_run_font(r, ascii_font=HEI, cjk_font=HEI, size=SZ_H1, bold=True)
    for i, ref in enumerate(REFERENCES, 1):
        p = add_par(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=2, line=1.05)
        p.paragraph_format.left_indent = Pt(16)
        p.paragraph_format.first_line_indent = Pt(-16)
        r = p.add_run(f"[{i}]  ")
        set_run_font(r, ascii_font=TNR, cjk_font=SONG, size=8.5)
        r = p.add_run(ref)
        set_run_font(r, ascii_font=TNR, cjk_font=SONG, size=8.5)


REFERENCES = [
    "周荣义, 林金玉, 刘勇. 危险货物道路运输风险评估的集对模型及应用[J]. 中国安全科学学报, 2019, 29(1): 173-179.\n"
    "Zhou Rongyi, Lin Jinyu, Liu Yong. A risk assessment model for hazmat road transportation based on set pair "
    "analysis and its application[J]. China Safety Science Journal, 2019, 29(1): 173-179.",

    "马晓丽, 倪安宁, 谢晓忠, 等. 城市道路危险货物运输风险评估[J]. 中国安全科学学报, 2018, 28(5): 178-183.\n"
    "Ma Xiaoli, Ni Anning, Xie Xiaozhong, et al. Research on assessment of risk in hazardous materials transportation "
    "on urban road[J]. China Safety Science Journal, 2018, 28(5): 178-183.",

    "闫胜煜, 郝佳琪, 刘洋, 等. 基于熵权-TOPSIS的省域道路货运企业运营安全评估方法[J]. 重庆交通大学学报"
    "(自然科学版), 2025, 44(8): 116-122.\n"
    "Yan Shengyu, Hao Jiaqi, Liu Yang, et al. Evaluation method for operational safety of provincial road freight "
    "enterprises based on entropy weight-TOPSIS[J]. Journal of Chongqing Jiaotong University (Natural Science), "
    "2025, 44(8): 116-122.",

    "武荣, 陈少阳, 崔华. 基于熵TOPSIS模型的大宗货物运输方式综合评价[J]. 重庆理工大学学报(自然科学), "
    "2022, 36(6): 254-260.\n"
    "Wu Rong, Chen Shaoyang, Cui Hua. Evaluation of bulk goods transportation mode based on entropy TOPSIS "
    "method[J]. Journal of Chongqing University of Technology (Natural Science), 2022, 36(6): 254-260.",

    "欧阳中辉, 樊辉锦, 陈青华, 等. 基于北斗短报文的特种车辆状态信息压缩传输方法研究[J]. 兵器装备工程学报, "
    "2020, 41(9): 124-129.\n"
    "Ouyang Zhonghui, Fan Huijin, Chen Qinghua, et al. Research on compression transmission method of special "
    "vehicle status information based on BeiDou short message[J]. Journal of Ordnance Equipment Engineering, "
    "2020, 41(9): 124-129.",

    "Hwang C L, Yoon K. Multiple attribute decision making: methods and applications[M]. Berlin: Springer-Verlag, "
    "1981: 58-191.",

    "Diakoulaki D, Mavrotas G, Papayannakis L. Determining objective weights in multiple criteria problems: the "
    "CRITIC method[J]. Computers & Operations Research, 1995, 22(7): 763-770.",

    "Shannon C E. A mathematical theory of communication[J]. The Bell System Technical Journal, 1948, 27(3): "
    "379-423.",

    "Hochreiter S, Schmidhuber J. Long short-term memory[J]. Neural Computation, 1997, 9(8): 1735-1780.",

    "Che Z, Purushotham S, Cho K, et al. Recurrent neural networks for multivariate time series with missing "
    "values[J]. Scientific Reports, 2018, 8: 6085.",

    "Malhotra P, Ramakrishnan A, Anand G, et al. LSTM-based encoder-decoder for multi-sensor anomaly "
    "detection[C]//Proceedings of the ICML 2016 Anomaly Detection Workshop. New York: ICML, 2016: 1-5.",

    "Vaswani A, Shazeer N, Parmar N, et al. Attention is all you need[C]//Advances in Neural Information "
    "Processing Systems 30. Long Beach: Curran Associates, 2017: 5998-6008.",

    "Kingma D P, Ba J. Adam: a method for stochastic optimization[C]//Proceedings of the 3rd International "
    "Conference on Learning Representations. San Diego: ICLR, 2015: 1-15.",

    "Rousseeuw P J. Silhouettes: a graphical aid to the interpretation and validation of cluster analysis[J]. "
    "Journal of Computational and Applied Mathematics, 1987, 20: 53-65.",

    "Hubert L, Arabie P. Comparing partitions[J]. Journal of Classification, 1985, 2(1): 193-218.",

    "Kruskal W H, Wallis W A. Use of ranks in one-criterion variance analysis[J]. Journal of the American "
    "Statistical Association, 1952, 47(260): 583-621.",

    "Hermans E, Brijs T, Wets G, et al. Benchmarking road safety: lessons to learn from a data envelopment "
    "analysis[J]. Accident Analysis & Prevention, 2009, 41(1): 174-182.",

    "交通运输部. 道路运输车辆动态监督管理办法[S]. 北京: 交通运输部, 2022.\n"
    "Ministry of Transport of the People's Republic of China. Measures for the dynamic supervision and "
    "administration of road transport vehicles[S]. Beijing: Ministry of Transport, 2022.",
]


if __name__ == "__main__":
    build()
