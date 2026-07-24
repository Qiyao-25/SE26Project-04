import { useEffect, useRef, useState } from 'react';
import { Empty, Spin, Typography } from 'antd';
import { getDocument, GlobalWorkerOptions, TextLayer } from 'pdfjs-dist';
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { API_BASE_URL } from '../../../services/runtimeConfig';
import { pushAnnotationSelection, readDomSelection } from '../../../utils/annotationSelection';

GlobalWorkerOptions.workerSrc = workerSrc;

const { Text } = Typography;
const MAX_PAGES = 40;
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

export default function PaperPdfViewer({
  paperId,
  pdfUrl,
  className = '',
  fullscreen = false,
  onSelectText,
}) {
  const hostRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [pageCount, setPageCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const host = hostRef.current;
    if (!host) return undefined;

    const source = resolvePdfSource(paperId, pdfUrl);
    if (!source) {
      setLoading(false);
      setError('当前论文没有可读取的 PDF');
      return undefined;
    }

    setLoading(true);
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

        if (!cancelled) setLoading(false);
      } catch (err) {
        if (cancelled) return;
        setLoading(false);
        setError(err?.message || 'PDF 加载失败');
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

  const handleMouseUp = () => {
    const read = readDomSelection(hostRef.current);
    if (!read || read.text.length < 1) return;
    const payload = { text: read.text };
    pushAnnotationSelection(payload);
    onSelectText?.(read.text);
  };

  if (!pdfUrl && !(paperId && /^\d+$/.test(String(paperId)))) {
    return <Empty description="当前论文没有可读取的 PDF" />;
  }

  return (
    <div className={`paper-pdf-viewer ${fullscreen ? 'is-fullscreen' : ''} ${className}`.trim()}>
      {loading ? (
        <div className="paper-pdf-viewer-status">
          <Spin tip="正在加载可划词 PDF..." />
        </div>
      ) : null}
      {error ? (
        <div className="paper-pdf-viewer-status">
          <Empty description={error} />
          {pdfUrl ? (
            <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
              可改用「新窗口打开 PDF」；同源代理失败时通常是外网拉取受阻。
            </Text>
          ) : null}
        </div>
      ) : null}
      <div
        ref={hostRef}
        className="paper-pdf-pages"
        onMouseUp={handleMouseUp}
        role="document"
        aria-label="可划选 PDF 正文"
      />
      {!loading && !error && pageCount > MAX_PAGES ? (
        <Text type="secondary" className="paper-pdf-viewer-note">
          在线预览前 {MAX_PAGES} 页（共 {pageCount} 页），完整内容请新窗口打开 PDF。
        </Text>
      ) : null}
    </div>
  );
}
