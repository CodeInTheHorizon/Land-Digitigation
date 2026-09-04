interface Props {
  title: string;
  description?: string;
}

export default function PlaceholderPage({ title, description }: Props) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center py-20">
      <h2 className="text-2xl font-bold text-slate-700">{title}</h2>
      <p className="text-slate-500 mt-2 max-w-md">
        {description ?? "This page will be implemented in a future phase."}
      </p>
    </div>
  );
}
