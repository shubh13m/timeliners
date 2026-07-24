import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-12 text-center">
      <h1 className="mb-2 text-2xl font-bold text-white">Story not found</h1>
      <p className="mb-4 text-gray-400">
        It may have been archived or the link is incorrect.
      </p>
      <Link href="/" className="text-blue-400 hover:underline">
        ← Back to feed
      </Link>
    </div>
  );
}
