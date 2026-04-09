"use client";

import React from 'react';

export function PlatformShell({ breadcrumbs, children }: { breadcrumbs?: React.ReactNode; children: React.ReactNode }) {
  return <div className="platform-shell"><div className="platform-shell__inner">{breadcrumbs ? <div className="platform-shell__breadcrumbs">{breadcrumbs}</div> : null}<main>{children}</main></div></div>;
}
