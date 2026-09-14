import styles from "./synapse-constellation.module.css";

// Açık uçlu yollar, bir organ ya da simge çizmeden bağlantı hissi verir.
const fibres = [
  "M39 249C78 253 89 207 124 208C162 209 181 141 227 141",
  "M239 141C280 140 283 190 332 190",
  "M342 184C360 165 354 122 389 101",
  "M335 196C326 215 315 250 291 260",
  "M129 214C165 249 221 222 280 260",
  "M124 208C110 193 100 177 73 179M103 194C86 205 63 199 53 184M90 181C89 166 74 152 55 154",
  "M124 208C103 217 94 240 96 264M103 237C82 237 68 254 65 269",
  "M124 208C135 180 123 165 138 147M128 173C142 172 151 157 149 142",
  "M233 141C212 117 189 124 175 103M208 121C212 102 200 88 181 83",
  "M233 141C240 115 250 97 276 85M252 103C242 84 249 68 263 57",
  "M233 141C217 153 219 176 195 184M219 168C237 183 223 201 208 207",
  "M338 190C362 190 378 206 402 198M377 200C382 184 399 177 416 182",
  "M338 190C347 214 364 234 390 240M363 229C355 247 365 260 383 267",
  "M393 96C413 99 424 87 445 91M421 91C425 74 441 64 454 69",
  "M393 96C380 81 389 61 407 49M389 75C371 77 359 65 358 50",
  "M393 96C399 117 419 122 440 112M422 120C425 140 439 145 458 140",
  "M286 263C265 275 251 268 232 280M260 272C250 258 235 257 224 262",
  "M286 263C300 281 321 277 337 289M312 278C311 258 327 254 337 260",
];
const nodes = [[124,208],[233,141],[338,190],[393,96],[286,263],[39,249],[55,154],[65,269],[149,142],[181,83],[263,57],[208,207],[416,182],[383,267],[454,69],[358,50],[458,140],[232,280],[337,289]];

/** Soyut marka çizimi; öğrenci verisi veya ölçülmüş sinirsel etkinlik değildir. */
export function SynapseConstellation({ className = "" }: { className?: string }) {
  return <div className={`${styles.art} ${className}`}>
    <svg viewBox="0 0 500 330" fill="none" aria-hidden="true" className={styles.drawing}>
      <g stroke="currentColor" strokeWidth=".8" strokeLinecap="round" strokeLinejoin="round">
        {fibres.map((d,i)=><path key={i} d={d} opacity={i < 5 ? .62 : .36} />)}
      </g>
      <g stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" className={styles.signal}>
        {[0,1,2,3].map((index,i)=><path key={index} d={fibres[index]} pathLength="100" className={styles.trace} style={{animationDelay:`${i * .32}s`}} />)}
      </g>
      <g fill="currentColor">
        {nodes.map(([x,y],i)=><g key={i}><circle cx={x} cy={y} r={i < 5 ? "3" : "1.5"} opacity={i < 5 ? ".85" : ".4"} /><circle cx={x} cy={y} r="6" className={styles.node} style={{animationDelay:`${(i % 6) * .42}s`}} /></g>)}
      </g>
    </svg>
  </div>;
}
