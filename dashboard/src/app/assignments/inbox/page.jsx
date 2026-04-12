import { redirect } from 'next/navigation';

export default function InboxRedirect() {
  redirect('/grades?filter=review');
}
