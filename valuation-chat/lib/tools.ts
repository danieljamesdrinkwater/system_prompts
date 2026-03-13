import { tool } from "ai";
import { z } from "zod";

export const tools = {
  searchPricing: tool({
    description:
      "Search the web for recent sold prices and market values of an item. " +
      "Use this to find real pricing data from eBay sold listings, marketplace sales, etc. " +
      "Call this after identifying what the item is from the image.",
    inputSchema: z.object({
      query: z
        .string()
        .describe(
          'Search query for finding sold prices. Include specific item details like brand, model, condition. Example: "iPhone 14 Pro 256GB used sold price"'
        ),
    }),
    execute: async ({ query }) => {
      const serpApiKey = process.env.SERPAPI_KEY;

      if (serpApiKey) {
        try {
          const url = new URL("https://serpapi.com/search.json");
          url.searchParams.set("q", query + " sold price");
          url.searchParams.set("api_key", serpApiKey);
          url.searchParams.set("num", "10");
          const res = await fetch(url.toString());
          const data = await res.json();
          const results = (data.organic_results || [])
            .slice(0, 8)
            .map(
              (r: { title?: string; snippet?: string; link?: string }) =>
                `${r.title}\n${r.snippet}\n${r.link}`
            )
            .join("\n\n");
          return results || "No pricing results found. Provide your best estimate based on your knowledge.";
        } catch {
          return "Search failed. Provide your best estimate based on your knowledge.";
        }
      }

      return "Live search is not configured (no SERPAPI_KEY). Provide your best estimate based on your training data, and let the user know that estimates would be more accurate with live market data.";
    },
  }),
};
