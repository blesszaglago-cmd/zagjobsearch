import {Suspense} from 'react';
import type {Metadata} from 'next';
export const metadata:Metadata={title:'Opportunity details',robots:{index:false,follow:false}};
export default function Layout({children}:{children:React.ReactNode}){return <Suspense fallback={<p>Loading opportunity…</p>}>{children}</Suspense>}
