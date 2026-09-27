import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { tap } from 'rxjs';

export const TOKEN_KEY = 'lv_token';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);
  const token  = localStorage.getItem(TOKEN_KEY);

  const authed = token
    ? next(req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }))
    : next(req);

  return authed.pipe(
    tap({ error: (err) => {
      if (err instanceof HttpErrorResponse && err.status === 401) {
        localStorage.removeItem(TOKEN_KEY);
        router.navigate(['/login'], { queryParams: { expired: 'true' } });
      }
    }}),
  );
};
