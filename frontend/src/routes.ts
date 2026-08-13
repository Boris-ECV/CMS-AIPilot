export const LOGIN_PATH = "/login";
export const ARTICLES_PATH = "/articles";
export const ARTICLE_NEW_PATH = "/articles/new";
export const ARTICLE_EDIT_PATH = "/articles/:id/edit";

export function editPath(id: string): string {
  return `/articles/${id}/edit`;
}
