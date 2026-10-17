import { ImageResponse } from "next/og";
export const alt="ZagJobSearch. Find work. Find your direction.";
export const size={width:1200,height:630};
export const contentType="image/png";
export default function Image(){return new ImageResponse(<div style={{width:"100%",height:"100%",display:"flex",flexDirection:"column",background:"#fcd116",padding:80,color:"#111111"}}><div style={{display:"flex",fontSize:32,marginBottom:60}}>ZagJobSearch.</div><div style={{display:"flex",fontSize:78,fontWeight:700}}>Find work.</div><div style={{display:"flex",fontSize:78,fontWeight:700}}>Find your direction.</div><div style={{display:"flex",fontSize:28,marginTop:40}}>Ghana jobs. Internships. Scholarships. Your next step.</div></div>,size)}
