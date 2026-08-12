import { Navigate, Outlet } from "react-router-dom";
import { getStoredToken } from "./token";
import { LOGIN_PATH } from "../routes";

export function RequireAuth() {
  const token = getStoredToken();
  if (!token) {
    return <Navigate to={LOGIN_PATH} replace />;
  }
  return <Outlet />;
}
