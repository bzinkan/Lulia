'use client';
/**
 * /clips — legacy generation page.
 *
 * As of the video-library overhaul (decision #23 in CLAUDE.md: "Video = library,
 * not generator"), on-demand clip generation is no longer exposed in the UI.
 * Teachers browse premade Lulia-signature clips + their own uploads at
 * /videos/library instead. The generation backend (Veo, Leonardo previews,
 * clip_generation Inngest workflow) is still intact behind the API for when
 * we re-enable the prompt flow.
 *
 * This route just redirects to /videos/library so bookmarks + sidebar links
 * still land in a sensible place.
 */
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';

export default function ClipsLegacyRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/videos/library?video_kind=short_clip');
  }, [router]);

  return (
    <div className="flex items-center justify-center h-[60vh]" style={{ color: 'var(--text-mid)' }}>
      <div className="text-center">
        <Loader2 className="w-8 h-8 mx-auto mb-3 animate-spin" style={{ color: 'var(--coral)' }} />
        <p className="text-[14px]">Redirecting to Video Library…</p>
      </div>
    </div>
  );
}
