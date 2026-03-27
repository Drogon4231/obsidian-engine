export const Letterbox: React.FC = () => {
  const barH = 70;
  return (
    <>
      <div style={{position:'absolute',top:0,left:0,right:0,height:barH,
        background:'linear-gradient(180deg,#000000 60%,transparent)',zIndex:100}}/>
      <div style={{position:'absolute',bottom:0,left:0,right:0,height:barH,
        background:'linear-gradient(0deg,#000000 60%,transparent)',zIndex:100}}/>
    </>
  );
};
