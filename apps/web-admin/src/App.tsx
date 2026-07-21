import { useQuery } from "@tanstack/react-query";

async function fetchHealth() {
  return { status: "ok", service: "web-admin" };
}

export default function App() {
  const { data } = useQuery({ queryKey: ["health"], queryFn: fetchHealth });

  return (
    <div className="mx-auto max-w-4xl p-8">
      <h1 className="text-2xl font-bold">AI Enterprise OS Admin Console</h1>
      <p className="mt-3 text-slate-700">
        Platform status: <span className="font-semibold">{data?.status ?? "loading"}</span>
      </p>
    </div>
  );
}
