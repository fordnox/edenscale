import {
  useMutation,
  type UseMutationOptions,
  type UseMutationResult,
} from "@tanstack/react-query"
import type { FetchResponse, MaybeOptionalInit } from "openapi-fetch"

import client from "@/lib/api"
import type { paths } from "@/lib/schema"

type MutationMethod = "post" | "put" | "patch" | "delete"

type HasMethod<T, M extends string> = T extends Record<M, unknown> ? true : false

type MutationPaths<M extends MutationMethod> = {
  [K in keyof paths]: HasMethod<paths[K], M> extends true ? K : never
}[keyof paths]

type DefaultMedia = `${string}/${string}`

type MutationOp<P extends keyof paths, M extends MutationMethod> = paths[P] extends Record<M, infer Op>
  ? Op
  : never

type MutationData<P extends keyof paths, M extends MutationMethod, Init> = NonNullable<
  Awaited<FetchResponse<MutationOp<P, M>, Init, DefaultMedia>>["data"]
>

type MutationError<P extends keyof paths, M extends MutationMethod, Init> = NonNullable<
  Awaited<FetchResponse<MutationOp<P, M>, Init, DefaultMedia>>["error"]
>

const METHOD_FN = {
  post: "POST",
  put: "PUT",
  patch: "PATCH",
  delete: "DELETE",
} as const

type ExtraMutationOptions<TData, TError, TVariables> = Omit<
  UseMutationOptions<TData, TError, TVariables>,
  "mutationFn"
>

export function useApiMutation<
  M extends MutationMethod,
  P extends MutationPaths<M>,
  Init extends MaybeOptionalInit<paths[P], M>,
>(
  method: M,
  path: P,
  options?: ExtraMutationOptions<MutationData<P, M, Init>, MutationError<P, M, Init>, Init>,
): UseMutationResult<MutationData<P, M, Init>, MutationError<P, M, Init>, Init> {
  return useMutation<MutationData<P, M, Init>, MutationError<P, M, Init>, Init>({
    mutationFn: async (variables: Init) => {
      const fnKey = METHOD_FN[method]
      const fn = (client as unknown as Record<string, (p: P, init: Init) => Promise<{ data?: unknown; error?: unknown }>>)[fnKey]
      const { data, error } = await fn(path, variables)
      if (error) {
        throw error as MutationError<P, M, Init>
      }
      return data as MutationData<P, M, Init>
    },
    ...(options ?? {}),
  })
}
