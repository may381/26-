import { ShieldCheck, AudioLines, MessageCircle, ScanFace } from 'lucide-react';

/** Decorative only: each layer owns a transform so hover never interrupts floating. */
export default function FloatingStickers({ compact = false }: { compact?: boolean }) {
  const icons = [ShieldCheck, AudioLines, MessageCircle, ScanFace];
  return <div className={`floating-stickers ${compact ? 'stickers-compact' : ''}`} aria-hidden="true">
    {icons.map((Icon, index) => <span className={`sticker-position sticker-${index}`} key={index}>
      <span className="sticker-float"><span className="sticker-rock"><span className="sticker-art">
        <Icon size={36} strokeWidth={2.2} />
      </span></span></span>
    </span>)}
  </div>;
}
