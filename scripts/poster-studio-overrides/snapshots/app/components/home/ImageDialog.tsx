/**
 * 统一图片对话框
 * 包含三个Tab：本地上传、图库选择、网络搜图
 */

'use client';

import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Upload, Image as ImageIcon, X } from 'lucide-react';
import { getImageLibrary, ImageLibraryItem } from '@/lib/image-library';
import GrsImageLibrary from './GrsImageLibrary';

interface ImageDialogProps {
  open: boolean;
  onClose: () => void;
  onLocalUpload: () => void;
  onSelectImage: (url: string) => void;
}

export default function ImageDialog({
  open,
  onClose,
  onLocalUpload,
  onSelectImage,
}: ImageDialogProps) {
  const [activeTab, setActiveTab] = useState<'upload' | 'library' | 'grs'>('grs');
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  // 图库相关
  const [libraryImages, setLibraryImages] = useState<ImageLibraryItem[]>([]);
  const [libraryPage, setLibraryPage] = useState(1);
  const LIBRARY_PER_PAGE = 10; // 改为 10 张/页

  // 加载图片库
  const loadLibrary = () => {
    const library = getImageLibrary();
    setLibraryImages(library.getImages());
  };

  // 初始加载图库
  useEffect(() => {
    if (open && activeTab === 'library') {
      loadLibrary();
      setLibraryPage(1); // 重置到第一页
    }
  }, [open, activeTab]);

  // 选择图库图片
  const handleSelectLibraryImage = (url: string) => {
    onSelectImage(url);
    onClose();
  };

  // 删除图库图片
  const handleDeleteLibraryImage = (url: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const library = getImageLibrary();
    library.removeImage(url);
    loadLibrary();
  };

  // 触发本地上传
  const handleTriggerUpload = () => {
    onLocalUpload();
    onClose();
  };

  // 计算图库分页
  const paginatedLibraryImages = React.useMemo(() => {
    const startIndex = (libraryPage - 1) * LIBRARY_PER_PAGE;
    const endIndex = startIndex + LIBRARY_PER_PAGE;
    return libraryImages.slice(startIndex, endIndex);
  }, [libraryImages, libraryPage]);

  const totalLibraryPages = Math.ceil(libraryImages.length / LIBRARY_PER_PAGE);

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-5xl h-[calc(85vh+10px)] flex flex-col p-0">
        <DialogTitle className="sr-only">插入图片</DialogTitle>
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)} className="flex-1 flex flex-col">
          <TabsList className="mx-6 mt-6 mb-0 grid grid-cols-3 w-auto border-b rounded-none bg-transparent">
            <TabsTrigger value="grs" className="flex items-center gap-2">
              <ImageIcon className="h-4 w-4" />
              <span>GRS AI 图库</span>
            </TabsTrigger>
            <TabsTrigger value="library" className="flex items-center gap-2">
              <ImageIcon className="h-4 w-4" />
              <span>图库选择</span>
            </TabsTrigger>
            <TabsTrigger value="upload" className="flex items-center gap-2">
              <Upload className="h-4 w-4" />
              <span>本地上传</span>
            </TabsTrigger>
          </TabsList>

          {/* GRS AI 已生图库 Tab */}
          <TabsContent value="grs" className="flex-1 flex flex-col min-h-0">
            <GrsImageLibrary
              onSelectImage={(url) => {
                onSelectImage(url);
                onClose();
              }}
            />
          </TabsContent>

          {/* 本地上传 Tab */}
          <TabsContent value="upload" className="flex-1 flex items-center justify-center p-6">
            <button
              onClick={handleTriggerUpload}
              className="flex flex-col items-center justify-center p-12 rounded-2xl bg-primary/5 hover:bg-primary/10 transition-all group cursor-pointer border-2 border-dashed border-primary/30 hover:border-primary max-w-md w-full"
            >
              <Upload className="h-20 w-20 text-primary mb-6 group-hover:scale-110 transition-transform" />
              <h3 className="text-xl font-semibold mb-2">上传本地图片</h3>
              <p className="text-muted-foreground text-center">
                点击选择图片上传<br />
                支持 JPG、PNG、GIF 等格式
              </p>
              <p className="text-sm text-muted-foreground mt-4">
                💡 上传的图片会自动保存到图库
              </p>
            </button>
          </TabsContent>

          {/* 🆕 共享素材 Tab */}

          {/* 图库选择 Tab */}
          <TabsContent value="library" className="flex-1 flex flex-col">
            {libraryImages.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground p-6">
                <ImageIcon className="h-16 w-16 mb-4 opacity-20" />
                <p className="text-lg">图片库为空</p>
                <p className="text-sm mt-2">上传或粘贴图片后会自动保存到这里</p>
              </div>
            ) : (
              <>
                <div className="flex-1 overflow-y-auto p-6">
                  <div className="grid grid-cols-5 gap-4">
                    {paginatedLibraryImages.map((item) => (
                      <div
                        key={item.url}
                        className="group relative aspect-square rounded-lg overflow-hidden border-2 border-border hover:border-primary cursor-pointer transition-all"
                        onClick={() => handleSelectLibraryImage(item.url)}
                      >
                        <img
                          src={item.url}
                          alt={item.filename || '图片'}
                          className="w-full h-full object-cover"
                          loading="lazy"
                        />
                        {/* 删除按钮 */}
                        <button
                          onClick={(e) => handleDeleteLibraryImage(item.url, e)}
                          className="absolute top-2 right-2 p-1.5 bg-black/60 hover:bg-black/80 text-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                          title="删除"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 分页控件 */}
                {totalLibraryPages > 1 && (
                  <div className="flex items-center justify-center gap-2 px-6 py-4 border-t">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setLibraryPage(p => Math.max(1, p - 1))}
                      disabled={libraryPage === 1}
                    >
                      上一页
                    </Button>
                    <span className="text-sm text-muted-foreground">
                      第 {libraryPage} / {totalLibraryPages} 页
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setLibraryPage(p => Math.min(totalLibraryPages, p + 1))}
                      disabled={libraryPage === totalLibraryPages}
                    >
                      下一页
                    </Button>
                  </div>
                )}
              </>
            )}
          </TabsContent>

          {/* 网络搜图 Tab */}
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
