import {Suspense} from 'react';
import type {Metadata} from 'next';
export const metadata:Metadata={title:'Opportunity details',description:'Review an opportunity, check its source and apply on the original website. Sign in to save it to your tracker or tailor your CV.',robots:{index:false,follow:false}};
export default function Layout({children}:{children:React.ReactNode}){return <Suspense fallback={<p>Loading opportunity…</p>}>{children}</Suspense>}
