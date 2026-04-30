import { useQuery, type UseQueryOptions, type UseQueryResult } from "@tanstack/react-query"
import type { FetchResponse, MaybeOptionalInit } from "openapi-fetch"

import client from "@/lib/api"
import type { paths } from "@/lib/schema"

type HasMethod<T, M extends string> = T extends Record<M, unknown> ? true : false

type GetPaths = {
  [K in keyof paths]: HasMethod<paths[K], "get"> extends true ? K : never
}[keyof paths]

type DefaultMedia = `${string}/${string}`

type GetData<P extends GetPaths, Init> = NonNullable<
  Awaited<FetchResponse<paths[P]["get"], Init, DefaultMedia>>["data"]
>

type GetError<P extends GetPaths, Init> = NonNullable<
  Awaited<FetchResponse<paths[P]["get"], Init, DefaultMedia>>["error"]
>

type ExtraQueryOptions<TData, TError> = Omit<
  UseQueryOptions<TData, TError, TData, readonly unknown[]>,
  "queryKey" | "queryFn"
>

export function useApiQuery<
  P extends GetPaths,
  Init extends MaybeOptionalInit<paths[P], "get">,
>(
  path: P,
  init?: Init,
  options?: ExtraQueryOptions<GetData<P, Init>, GetError<P, Init>>,
): UseQueryResult<GetData<P, Init>, GetError<P, Init>> {
  return useQuery<GetData<P, Init>, GetError<P, Init>, GetData<P, Init>, readonly unknown[]>({
    queryKey: [path, init] as const,
    queryFn: async () => {
      const { data, error } = await client.GET(path, init as never)
      if (error) {
        throw error
      }
      return data as GetData<P, Init>
    },
    ...(options ?? {}),
  })
}
