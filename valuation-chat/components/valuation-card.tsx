interface ValuationCardProps {
  content: string;
}

function extractField(content: string, field: string): string {
  const regex = new RegExp(`\\*\\*${field}\\*\\*:\\s*(.+)`, "i");
  const match = content.match(regex);
  return match ? match[1].trim() : "";
}

export function ValuationCard({ content }: ValuationCardProps) {
  const item = extractField(content, "Item");
  const condition = extractField(content, "Condition");
  const fmv = extractField(content, "Fair Market Value");
  const likelyPrice = extractField(content, "Most Likely Price");
  const basis = extractField(content, "Basis");

  return (
    <div className="overflow-hidden rounded-xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-white shadow-sm dark:border-emerald-800 dark:from-emerald-950/50 dark:to-zinc-900">
      {/* Header */}
      <div className="border-b border-emerald-200 bg-emerald-100/50 px-4 py-2 dark:border-emerald-800 dark:bg-emerald-900/30">
        <h3 className="text-sm font-semibold text-emerald-800 dark:text-emerald-300">
          Fair Market Valuation
        </h3>
      </div>

      <div className="space-y-3 p-4">
        {/* Item */}
        {item && (
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-zinc-400">
              Item
            </p>
            <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
              {item}
            </p>
          </div>
        )}

        {/* Condition */}
        {condition && (
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-zinc-400">
              Condition
            </p>
            <span
              className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                condition.toLowerCase().includes("excellent")
                  ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                  : condition.toLowerCase().includes("good")
                    ? "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400"
                    : condition.toLowerCase().includes("fair")
                      ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400"
                      : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400"
              }`}
            >
              {condition}
            </span>
          </div>
        )}

        {/* Price */}
        <div className="rounded-lg bg-white p-3 shadow-sm dark:bg-zinc-800">
          {fmv && (
            <div className="mb-1">
              <p className="text-xs font-medium uppercase tracking-wider text-zinc-400">
                Fair Market Value
              </p>
              <p className="text-lg font-bold text-emerald-700 dark:text-emerald-400">
                {fmv}
              </p>
            </div>
          )}
          {likelyPrice && (
            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-zinc-400">
                Most Likely Price
              </p>
              <p className="text-xl font-bold text-emerald-800 dark:text-emerald-300">
                {likelyPrice}
              </p>
            </div>
          )}
        </div>

        {/* Basis */}
        {basis && (
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-zinc-400">
              Basis
            </p>
            <p className="text-xs text-zinc-600 dark:text-zinc-400">{basis}</p>
          </div>
        )}
      </div>
    </div>
  );
}
