interface ImagePreviewProps {
  files: { file: File; preview: string }[];
  onRemove: (index: number) => void;
}

export function ImagePreview({ files, onRemove }: ImagePreviewProps) {
  return (
    <div className="mb-3 flex flex-wrap gap-2">
      {files.map((f, i) => (
        <div key={i} className="group relative">
          <img
            src={f.preview}
            alt={f.file.name}
            className="h-20 w-20 rounded-lg object-cover"
          />
          <button
            type="button"
            onClick={() => onRemove(i)}
            className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-xs text-white opacity-0 transition-opacity group-hover:opacity-100"
          >
            x
          </button>
        </div>
      ))}
    </div>
  );
}
