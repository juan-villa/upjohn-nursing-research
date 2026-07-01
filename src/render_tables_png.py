#!/usr/bin/env python
"""Render each LaTeX table in outputs/appendix_tables.tex to a tightly-cropped
PNG using a real LaTeX toolchain (pdflatex + pdftoppm), scientific styling."""
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / 'outputs' / 'appendix_tables.tex').read_text()
OUT = ROOT / 'figures' / 'tables'
OUT.mkdir(parents=True, exist_ok=True)

PREAMBLE = (
    r'\documentclass[border=12pt,varwidth=18cm]{standalone}'
    r'\usepackage{booktabs}\usepackage{amsmath}\usepackage{amssymb}'
    r'\begin{document}'
)


def brace_arg(s, start):
    """Return the balanced {...} argument beginning at s[start]=='{'."""
    depth, i = 0, start
    while i < len(s):
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                return s[start + 1:i], i + 1
        i += 1
    raise ValueError('unbalanced braces')


def split_tables(src):
    return re.findall(r'\\begin\{table\}.*?\\end\{table\}', src, flags=re.S)


def to_standalone(block):
    # caption
    cap = ''
    m = re.search(r'\\caption', block)
    if m:
        cap, _ = brace_arg(block, block.index('{', m.end()))
    # label
    lab = 'table'
    m = re.search(r'\\label\{(.*?)\}', block)
    if m:
        lab = m.group(1).replace('tab:', '')
    # strip float scaffolding; keep tabular + notes
    body = block
    body = re.sub(r'\\begin\{table\}\[[^\]]*\]', '', body)
    body = body.replace(r'\end{table}', '')
    body = body.replace(r'\centering', '')
    # remove the caption{...} and label{...} commands precisely
    if cap:
        body = body.replace('\\caption{' + cap + '}', '')
    body = re.sub(r'\\label\{[^}]*\}', '', body)
    head = (r'{\bfseries\large ' + cap + r'}\par\medskip ') if cap else ''
    doc = PREAMBLE + head + body.strip() + r'\end{document}'
    return lab, doc


def render(lab, doc):
    with tempfile.TemporaryDirectory() as d:
        tex = Path(d) / 't.tex'
        tex.write_text(doc)
        r = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', 't.tex'],
                           cwd=d, capture_output=True, text=True)
        pdf = Path(d) / 't.pdf'
        if not pdf.exists():
            print(f'  FAIL {lab}: {r.stdout[-400:]}')
            return False
        out = OUT / f'tab_{lab}'
        subprocess.run(['pdftoppm', '-png', '-r', '220', '-singlefile', str(pdf), str(out)],
                       check=True)
        print(f'  saved figures/tables/tab_{lab}.png')
        return True


for block in split_tables(SRC):
    lab, doc = to_standalone(block)
    render(lab, doc)
