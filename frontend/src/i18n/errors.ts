import { ApiError } from '../api'

type Translate = (key: string, named?: Record<string, unknown>) => string

export function translatedError(
  translate: Translate,
  cause: unknown,
  fallbackKey: string,
): string {
  if (cause instanceof ApiError) {
    return translate(`errors.${cause.code}`)
  }
  return translate(fallbackKey)
}

