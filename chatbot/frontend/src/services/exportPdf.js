import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';
import { policeSrc, centerSrc } from '../brandAssets';

/* Branded PDF export of the current conversation (تصدير التقرير).
   Builds an off-screen light-themed report — header with the official logos,
   then each question/answer with its charts — renders it with html2canvas and
   slices it into A4 pages with jsPDF. Entirely client-side. */

const A4_W = 210, A4_H = 297;           // mm
const REPORT_PX = 794;                  // A4 width at ~96dpi

async function svgToPngDataUrl(svgEl, scale = 2) {
  const xml = new XMLSerializer().serializeToString(svgEl);
  const img = new Image();
  await new Promise((res, rej) => {
    img.onload = res; img.onerror = rej;
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(xml);
  });
  const w = svgEl.clientWidth || svgEl.viewBox?.baseVal?.width || 640;
  const h = svgEl.clientHeight || svgEl.viewBox?.baseVal?.height || 260;
  const c = document.createElement('canvas');
  c.width = w * scale; c.height = h * scale;
  const ctx = c.getContext('2d');
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, c.width, c.height);
  ctx.drawImage(img, 0, 0, c.width, c.height);
  return { url: c.toDataURL('image/png'), w, h };
}

function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
}

export async function exportConversationPdf(chat) {
  const rows = document.querySelectorAll('.msgs > div');
  if (!rows.length) {
    alert('ابدأ محادثة أولاً ليتم تصدير التقرير — start a conversation first.');
    return;
  }

  // ── build the off-screen report ──
  const report = el('div', 'pdf-report');
  report.setAttribute('dir', 'rtl');
  report.style.cssText =
    `position:fixed;top:0;left:-12000px;width:${REPORT_PX}px;background:#ffffff;z-index:-1;`;

  const head = el('div', 'pdf-head');
  const logos = el('div', 'pdf-logos');
  if (policeSrc) {
    const police = el('img'); police.src = policeSrc; police.style.height = '46px';
    logos.appendChild(police);
  }
  if (centerSrc) {
    const center = el('img'); center.src = centerSrc; center.style.height = '40px';
    logos.appendChild(center);
  }
  head.appendChild(logos);
  head.appendChild(el('div', 'pdf-title',
    'تقرير المساعد الذكي <span class="en">· Smart Assistant Report</span>'));
  const now = new Date();
  head.appendChild(el('div', 'pdf-meta',
    `${chat?.title && chat.title !== 'محادثة جديدة' ? chat.title + ' — ' : ''}` +
    now.toLocaleDateString('ar-AE', { timeZone: 'Asia/Dubai', year: 'numeric', month: 'long', day: 'numeric' }) +
    ' · ' + now.toLocaleTimeString('en-GB', { timeZone: 'Asia/Dubai', hour12: false })));
  report.appendChild(head);

  for (const row of rows) {
    const userBubble = row.querySelector('.msg-user-bubble');
    const botBubble = row.querySelector('.msg-bot-bubble');

    if (userBubble) {
      const q = el('div', 'pdf-q');
      q.appendChild(el('div', 'pdf-q-label', 'السؤال'));
      q.appendChild(el('div', 'pdf-q-text', userBubble.innerHTML));
      report.appendChild(q);
    } else if (botBubble) {
      const a = el('div', 'pdf-a');
      a.appendChild(el('div', 'pdf-a-label', 'إجابة المساعد الذكي'));
      const body = el('div', 'pdf-a-body', botBubble.innerHTML);
      a.appendChild(body);
      // charts rendered in this row → embed as images
      for (const svg of row.querySelectorAll('svg.recharts-surface')) {
        try {
          const { url, w, h } = await svgToPngDataUrl(svg);
          const img = el('img', 'pdf-chart');
          img.src = url;
          img.style.width = '100%';
          img.style.aspectRatio = `${w}/${h}`;
          a.appendChild(img);
        } catch { /* skip un-serialisable chart */ }
      }
      report.appendChild(a);
    }
  }

  report.appendChild(el('div', 'pdf-foot',
    'شرطة دبي — مركز التحليل والتنبؤ الأمني · Dubai Police — Security Analytics & Forecast Center'));
  document.body.appendChild(report);

  try {
    await new Promise(r => setTimeout(r, 250));   // let images/fonts settle
    const canvas = await html2canvas(report, {
      scale: 2, backgroundColor: '#ffffff', useCORS: true, logging: false,
    });

    const pdf = new jsPDF('p', 'mm', 'a4');
    const imgData = canvas.toDataURL('image/jpeg', 0.94);
    const imgH = (canvas.height * A4_W) / canvas.width;
    let heightLeft = imgH, pos = 0;
    pdf.addImage(imgData, 'JPEG', 0, pos, A4_W, imgH);
    heightLeft -= A4_H;
    while (heightLeft > 0) {
      pos -= A4_H;
      pdf.addPage();
      pdf.addImage(imgData, 'JPEG', 0, pos, A4_W, imgH);
      heightLeft -= A4_H;
    }

    const stamp = now.toISOString().slice(0, 10);
    pdf.save(`Smart_Assistant_Report_${stamp}.pdf`);
  } finally {
    report.remove();
  }
}
