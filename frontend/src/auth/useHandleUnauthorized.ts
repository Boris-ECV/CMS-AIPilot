import { useNavigate } from "react-router-dom";
import { clearStoredToken } from "./token";
import { LOGIN_PATH } from "../routes";

/**
 * Shared 401 handler for pages that call protected APIs directly (outside
 * of route entry, where `RequireAuth` only checks token presence, not
 * expiry). Clears the stored token and navigates to the login page, the
 * same effect `RequireAuth` produces when no token is present.
 */
export function useHandleUnauthorized(): () => void {
  const navigate = useNavigate();
  return () => {
    clearStoredToken();
    navigate(LOGIN_PATH, { replace: true });
  };
}
