'use client';

/**
 * GRS AI 已生图库 — lists every image generated on the grsai-studio site
 * (scanned from output/ by FastAPI /api/poster/library). Manual refresh
 * picks up images generated after the dialog was opened.
 *
 * Paginated: 20 thumbnails per page in a 4-column grid (4×5). Injected as a
 * tab in ImageDialog; selecting an image calls onSelectImage(url), the same
 * contract the other tabs use to place an image on the canvas.
 */

import { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Loader2, Image as ImageIcon, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';

const GRSAI_ORIGIN = process.env.NEXT_PUBLIC_GRSAI_ORIGIN || 'http://127.0.0.1:8099';
const PAGE_SIZE = 20;

interface GrsImage {
  id: string;
  url: string;
  name: string;
}

interface GrsImageLibraryProps {
  onSelectImage: (url: string) => void;
}

export default function GrsImageLibrary({ onSelectImage }: GrsImageLibraryProps) {
  const [images, setImages] = useState<GrsImage[]>([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${GRSAI_ORIGIN}/api/poster/library`, {
        cache: 'no-store',
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setImages(data.images || []);
      setPage(1);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const totalPages = Math.max(1, Math.ceil(images.length / PAGE_SIZE));
  const pageImages = images.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <div className="flex flex-col">
      {/* 头部：计数 + 刷新 */}
      <div className="px-6 pt-6 pb-4 flex items-center justify-between shrink-0">
        <p className="text-sm text-muted-foreground">
          {loaded ? `共 ${images.length} 张 GRS AI 生成图（最新在前）` : '加载中...'}
        </p>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          {loading ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4 mr-2" />
          )}
          刷新
        </Button>
      </div>

      {/* 图片网格（可滚动，4×5）。max-h 显式限高，避免宽屏下 flex 链不收敛导致溢出 */}
      <div className="overflow-y-auto px-6 max-h-[55vh]">
        {error ? (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <p className="text-lg">加载失败</p>
            <p className="text-sm mt-2">{error}</p>
            <Button variant="outline" size="sm" className="mt-4" onClick={load}>
              重试
            </Button>
          </div>
        ) : pageImages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <ImageIcon className="h-16 w-16 mb-4 opacity-20" />
            <p className="text-lg">暂无生成图</p>
            <p className="text-sm mt-2">
              在 GRS AI 工作台生成图片后，回到这里点「刷新」即可看到
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-4 gap-4 pb-2">
            {pageImages.map((img, idx) => (
              <div
                key={`${page}-${idx}-${img.id}`}
                className="group relative aspect-square rounded-lg overflow-hidden border-2 border-border hover:border-primary cursor-pointer transition-all"
                onClick={() => onSelectImage(img.url)}
                title={img.name}
              >
                <img
                  src={img.url}
                  alt={img.name}
                  className="w-full h-full object-cover"
                  loading="lazy"
                  crossOrigin="anonymous"
                />
                <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <p className="text-white text-xs truncate">{img.name}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 分页 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 px-6 py-3 border-t shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            <ChevronLeft className="h-4 w-4" />
            上一页
          </Button>
          <span className="text-sm text-muted-foreground">
            {page} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            下一页
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
