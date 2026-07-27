import { useEffect, useRef, useState } from 'react';
import { Empty, Spin, Typography } from 'antd';
import { getDocument, GlobalWorkerOptions, TextLayer } from 'pdfjs-dist';
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { API_BASE_URL } from '../../../services/runtimeConfig';
import { pushAnnotationSelection, readDomSelection } from '../../../utils/annotationSelection';

GlobalWorkerOptions.workerSrc = workerSrc;

const { Text } = Typography;
const MAX_PAGES = 60;
const SCALE = 1.25;

function authHeaders() {
  const token = localStorage.getItem('papermate.accessToken');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function resolvePdfSource(paperId, externalPdfUrl) {
  if (paperId && /^\d+$/.test(String(paperId))) {
    const base = String(API_BASE_URL || '/api').replace(/\/$/, '');
    return {
      url: `${base}/papers/${paperId}/pdf`,
      httpHeaders: authHeaders(),
      withCredentials: false,
    };
  }
  if (externalPdfUrl) {
    return { url: externalPdfUrl };
  }
  return null;
}

function normalizeRects(range, pageEl) {
  if (!range || !pageEl) return [];
  const pageBox = pageEl.getBoundingClientRect();
  if (!pageBox.width || !pageBox.height) return [];
  return Array.from(range.getClientRects())
    .map((rect) => ({
      x: (rect.left - pageBox.left) / pageBox.width,
      y: (rect.top - pageBox.top) / pageBox.height,
      w: rect.width / pageBox.width,
      h: rect.height / pageBox.height,
    }))
    .filter((item) => item.w > 0.002 && item.h > 0.002);
}

function clearHighlightLayers(host) {
  host?.querySelectorAll('.pdf-highlight-layer').forEach((node) => node.remove());
}

function paintHighlights(host, highlights) {
  clearHighlightLayers(host);
  if (!host || !Array.isArray(highlights) || highlights.length < 1) return;

  const byPage = new Map();
  highlights.forEach((item) => {
    const page = Number(item?.pageNo || item?.page_no || 0);
    const rects = item?.rects || item?.highlight_rects || [];
    if (!page || !Array.isArray(rects) || rects.length < 1) return;
    const list = byPage.get(page) || [];
    list.push({
      rects,
      color: item.color || item.highlight_color || '#fde68a',
      id: item.id,
    });
    byPage.set(page, list);
  });

  byPage.forEach((entries, pageNo) => {
    const pageEl = host.querySelector(`.pdf-page[data-page-number="${pageNo}"]`);
    if (!pageEl) return;
    const layer = document.createElement('div');
    layer.className = 'pdf-highlight-layer';
    entries.forEach((entry) => {
      entry.rects.forEach((rect) => {
        const mark = document.createElement('div');
        mark.className = 'pdf-highlight-rect';
        mark.style.left = `${(rect.x || 0) * 100}%`;
        mark.style.top = `${(rect.y || 0) * 100}%`;
        mark.style.width = `${(rect.w || 0) * 100}%`;
        mark.style.height = `${(rect.h || 0) * 100}%`;
        mark.style.background = entry.color;
        if (entry.id) mark.dataset.annotationId = String(entry.id);
        layer.appendChild(mark);
      });
    });
    pageEl.appendChild(layer);
  });
}

export default function PaperPdfViewer({
  paperId,
  pdfUrl,
  className = '',
  fullscreen = false,
  highlights = [],
  onSelectText,
}) {
  const hostRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [pageCount, setPageCount] = useState(0);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const host = hostRef.current;
    if (!host) return undefined;

    const source = resolvePdfSource(paperId, pdfUrl);
    if (!source) {
      setLoading(false);
      setReady(false);
      setError('褰撳墠璁烘枃娌℃湁鍙鍙栫殑 PDF');
      return undefined;
    }

    setLoading(true);
    setReady(false);
    setError('');
    host.innerHTML = '';

    const tasks = [];
    const loadingTask = getDocument(source);

    (async () => {
      try {
        const pdf = await loadingTask.promise;
        if (cancelled) return;
        const total = Math.min(pdf.numPages || 0, MAX_PAGES);
        setPageCount(pdf.numPages || 0);

        for (let pageNumber = 1; pageNumber <= total; pageNumber += 1) {
          if (cancelled) return;
          const page = await pdf.getPage(pageNumber);
          const viewport = page.getViewport({ scale: SCALE });

          const pageWrap = document.createElement('div');
          pageWrap.className = 'pdf-page';
          pageWrap.dataset.pageNumber = String(pageNumber);
          pageWrap.style.width = `${viewport.width}px`;
          pageWrap.style.height = `${viewport.height}px`;

          const canvas = document.createElement('canvas');
          canvas.className = 'pdf-page-canvas';
          canvas.width = viewport.width;
          canvas.height = viewport.height;
          pageWrap.appendChild(canvas);

          const textLayerDiv = document.createElement('div');
          textLayerDiv.className = 'textLayer';
          textLayerDiv.style.width = `${viewport.width}px`;
          textLayerDiv.style.height = `${viewport.height}px`;
          pageWrap.appendChild(textLayerDiv);

          host.appendChild(pageWrap);

          const renderTask = page.render({
            canvasContext: canvas.getContext('2d'),
            viewport,
          });
          tasks.push(renderTask);
          await renderTask.promise;

          const textContent = await page.getTextContent();
          const textLayer = new TextLayer({
            textContentSource: textContent,
            container: textLayerDiv,
            viewport,
          });
          await textLayer.render();
        }

        if (!cancelled) {
          setLoading(false);
          setReady(true);
        }
      } catch (err) {
        if (cancelled) return;
        setLoading(false);
        setReady(false);
        setError(err?.message || 'PDF 鍔犺浇澶辫触');
      }
    })();

    return () => {
      cancelled = true;
      tasks.forEach((task) => {
        try { task.cancel(); } catch { /* ignore */ }
      });
      try { loadingTask.destroy(); } catch { /* ignore */ }
      if (host) host.innerHTML = '';
    };
  }, [paperId, pdfUrl, fullscreen]);

  useEffect(() => {
    if (!ready || !hostRef.current) return;
    paintHighlights(hostRef.current, highlights);
  }, [ready, highlights]);

  const handleMouseUp = () => {
    const read = readDomSelection(hostRef.current);
    if (!read || read.text.length < 1) return;
    const pageEl = read.range?.commonAncestorContainer?.parentElement?.closest?.('.pdf-page')
      || read.range?.startContainer?.parentElement?.closest?.('.pdf-page');
    const pageNo = pageEl ? Number(pageEl.dataset.pageNumber || 0) || null : null;
    const rects = normalizeRects(read.range, pageEl);
    const payload = {
      text: read.text,
      pageNo,
      rects,
      highlightColor: '#fde68a',
    };
    pushAnnotationSelection(payload);
    onSelectText?.(payload);
  };

  if (!pdfUrl && !(paperId && /^\d+$/.test(String(paperId)))) {
    return <Empty description="褰撳墠璁烘枃娌℃湁鍙鍙栫殑 PDF" />;
  }

  return (
    <div className={`paper-pdf-viewer ${fullscreen ? 'is-fullscreen' : ''} ${className}`.trim()}>
      {loading ? (
        <div className="paper-pdf-viewer-status">
          <Spin tip="姝ｅ湪鍔犺浇鍙垝璇?PDF锛堝悓婧愮紦瀛橈級..." />
        </div>
      ) : null}
      {error ? (
        <div className="paper-pdf-viewer-status">
          <Empty description={error} />
          {pdfUrl ? (
            <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
              鍙敼鐢ㄣ€屾柊绐楀彛鎵撳紑 PDF銆嶏紱鍚屾簮缂撳瓨澶辫触鏃堕€氬父鏄缃戞媺鍙栧彈闃汇€?            </Text>
          ) : null}
        </div>
      ) : null}
      <div
        ref={hostRef}
        className="paper-pdf-pages"
        onMouseUp={handleMouseUp}
        role="document"
        aria-label="鍙垝閫?PDF 姝ｆ枃"
      />
      {!loading && !error && pageCount > MAX_PAGES ? (
        <Text type="secondary" className="paper-pdf-viewer-note">
          鍦ㄧ嚎棰勮鍓?{MAX_PAGES} 椤碉紙鍏?{pageCount} 椤碉級锛屽畬鏁村唴瀹硅鏂扮獥鍙ｆ墦寮€ PDF銆?        </Text>
      ) : null}
    </div>
  );
}
