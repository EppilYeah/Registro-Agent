let colunas = 50;
let linhas = 50;
let tamanhoPixel;

let estado = {
    r: 0, g: 255, b: 0,
    tamanhoPupila: 0.3,
    deformacao: 0.05,
    velocidadeMovimento: 0.02,
    intensidadeRespiracao: 0.03
};

let alvo = { ...estado };

let estaFalando = false;

let posicaoPupila = { x: 0, y: 0 };
let alvoOlhar = { x: 0, y: 0 };
let tempoUltimoSalto = 0;

let rastreamentoCamera = {
    ativo: false,
    x: 0,
    y: 0,
    ultimoUpdate: 0
};

let anguloEspiral = 0;
let pulsoLuz = 0;

const EXPRESSOES = {
    "neutro": {
        r: 0, g: 255, b: 0,
        tamanhoPupila: 0.3,
        deformacao: 0.05,
        velocidadeMovimento: 0.01,
        intensidadeRespiracao: 0.03,
        comportamentoPupila: "saltos_rapidos",
        formatoOlho: "circular"
    },
    "sarcasmo_tedio": {
        r: 100, g: 150, b: 255,
        tamanhoPupila: 0.4,
        deformacao: 0.08,
        velocidadeMovimento: 0.01,
        intensidadeRespiracao: 0.02,
        comportamentoPupila: "centralizado",
        formatoOlho: "meia_lua"
    },
    "irritado": {
        r: 255, g: 0, b: 0,
        tamanhoPupila: 0.15,
        deformacao: 0.5,
        velocidadeMovimento: 0.1,
        intensidadeRespiracao: 0.02,
        comportamentoPupila: "centralizado",
        formatoOlho: "erratico"
    },
    "confuso": {
        r: 255, g: 150, b: 0,
        tamanhoPupila: 0.38,
        deformacao: 0.12,
        velocidadeMovimento: 0.02,
        intensidadeRespiracao: 0.05,
        comportamentoPupila: "espiral",
        formatoOlho: "arregalado"  
    },
    "desconfiado": {
        r: 255, g: 255, b: 0,
        tamanhoPupila: 0.2,
        deformacao: 0.1,
        velocidadeMovimento: 0.02,
        intensidadeRespiracao: 0.03,
        comportamentoPupila: "observando_rapido",
        formatoOlho: "circular"
    },
    "arrogante": {
        r: 200, g: 0, b: 255,
        tamanhoPupila: 0.28,
        deformacao: 0.15,
        velocidadeMovimento: 0.02,
        intensidadeRespiracao: 0.04,
        comportamentoPupila: "cantos_lentos",
        formatoOlho: "distorcido_leve"
    },
    "feliz": {
        r: 0, g: 255, b: 200,
        tamanhoPupila: 0.35,
        deformacao: 0.12,
        velocidadeMovimento: 0.03,
        intensidadeRespiracao: 0.05,
        comportamentoPupila: "centro_com_saltos",
        formatoOlho: "circular"
    },
    "ouvindo": {
        r: 0, g: 180, b: 255,
        tamanhoPupila: 0.5,
        deformacao: 0.08,
        velocidadeMovimento: 0.02,
        intensidadeRespiracao: 0.04,
        comportamentoPupila: "centralizado",
        formatoOlho: "circular",
    }
};

let expressaoAtual = EXPRESSOES["neutro"];
let expressaoAlvo = EXPRESSOES["neutro"];
let progressoTransicao = 1.0;

eel.expose(jsAtualizarRosto);
function jsAtualizarRosto(emocao, falando) {
    estaFalando = falando;
    expressaoAlvo = EXPRESSOES[emocao] || EXPRESSOES["neutro"];
    
    if (expressaoAlvo !== expressaoAtual) {
        progressoTransicao = 0.0;
    }
    
    alvo.r = expressaoAlvo.r;
    alvo.g = expressaoAlvo.g;
    alvo.b = expressaoAlvo.b;
    alvo.tamanhoPupila = expressaoAlvo.tamanhoPupila;
    alvo.deformacao = expressaoAlvo.deformacao;
    alvo.velocidadeMovimento = expressaoAlvo.velocidadeMovimento;
    alvo.intensidadeRespiracao = expressaoAlvo.intensidadeRespiracao;
}

eel.expose(jsAtualizarOlhar);
function jsAtualizarOlhar(x, y, encontrouRosto) {
    rastreamentoCamera.ativo = encontrouRosto;
    rastreamentoCamera.x = x;
    rastreamentoCamera.y = y;
    rastreamentoCamera.ultimoUpdate = millis();
}

function setup() {
    createCanvas(windowWidth, windowHeight);
    noStroke();
    tamanhoPixel = min(width, height) / colunas;
    
    console.log("[UI] Canvas inicializado");
}

function draw() {
    background(10);
    
    let suavidade = 0.08;
    estado.r = lerp(estado.r, alvo.r, suavidade);
    estado.g = lerp(estado.g, alvo.g, suavidade);
    estado.b = lerp(estado.b, alvo.b, suavidade);
    estado.tamanhoPupila = lerp(estado.tamanhoPupila, alvo.tamanhoPupila, suavidade);
    estado.deformacao = lerp(estado.deformacao, alvo.deformacao, suavidade);
    estado.velocidadeMovimento = lerp(estado.velocidadeMovimento, alvo.velocidadeMovimento, suavidade);
    estado.intensidadeRespiracao = lerp(estado.intensidadeRespiracao, alvo.intensidadeRespiracao, suavidade);
    
    if (progressoTransicao < 1.0) {
        progressoTransicao += 0.015;
        progressoTransicao = min(progressoTransicao, 1.0);
    }
    
    atualizarPosicaoPupila();
    
    if (obterComportamentoAtual() === "espiral") {
        anguloEspiral += 0.1;
    }
    
    if (estaFalando) {
        pulsoLuz = sin(frameCount * 0.3) * 0.5 + 0.5;
    } else {
        pulsoLuz = lerp(pulsoLuz, 0, 0.1);
    }
    
    desenharOlho();
}

function obterComportamentoAtual() {
    let t = easeInOutCubic(progressoTransicao);
    
    if (t < 0.5) {
        return expressaoAtual.comportamentoPupila;
    } else {
        return expressaoAlvo.comportamentoPupila;
    }
}

function obterFormatoAtual() {
    let t = easeInOutCubic(progressoTransicao);
    
    if (t < 0.5) {
        return expressaoAtual.formatoOlho;
    } else {
        return expressaoAlvo.formatoOlho;
    }
}

function easeInOutCubic(t) {
    return t < 0.5 ? 4 * t * t * t : 1 - pow(-2 * t + 2, 3) / 2;
}

function atualizarPosicaoPupila() {
    if (rastreamentoCamera.ativo && millis() - rastreamentoCamera.ultimoUpdate < 2000) {
        posicaoPupila.x = lerp(posicaoPupila.x, rastreamentoCamera.x, 0.15);
        posicaoPupila.y = lerp(posicaoPupila.y, rastreamentoCamera.y, 0.15);
        return;
    }

    let comportamento = obterComportamentoAtual();

    switch (comportamento) {
        case "saltos_rapidos":
            if (millis() - tempoUltimoSalto > random(800, 1500)) {
                alvoOlhar.x = random(-4, 4);
                alvoOlhar.y = random(-4, 4);
                tempoUltimoSalto = millis();
            }
            posicaoPupila.x = lerp(posicaoPupila.x, alvoOlhar.x, 0.08);
            posicaoPupila.y = lerp(posicaoPupila.y, alvoOlhar.y, 0.08);
            break;
        
        case "centralizado":
            posicaoPupila.x = lerp(posicaoPupila.x, 0, 0.1);
            posicaoPupila.y = lerp(posicaoPupila.y, 0, 0.1);
            break;
        
        case "espiral":
            posicaoPupila.x = 0;
            posicaoPupila.y = 0;
            break;
        
        case "observando_rapido":
            if (millis() - tempoUltimoSalto > random(150, 400)) {
                alvoOlhar.x = random(-5, 5);
                alvoOlhar.y = random(-5, 5);
                tempoUltimoSalto = millis();
            }
            posicaoPupila.x = lerp(posicaoPupila.x, alvoOlhar.x, 0.25);
            posicaoPupila.y = lerp(posicaoPupila.y, alvoOlhar.y, 0.25);
            break;
        
        case "cantos_lentos":
            alvoOlhar.x = sin(frameCount * 0.02) * 3;
            alvoOlhar.y = cos(frameCount * 0.015) * 3;
            posicaoPupila.x = lerp(posicaoPupila.x, alvoOlhar.x, 0.03);
            posicaoPupila.y = lerp(posicaoPupila.y, alvoOlhar.y, 0.03);
            break;
        
        case "centro_com_saltos":
            if (millis() - tempoUltimoSalto > random(1000, 2000)) {
                alvoOlhar.x = random(-5, 5);
                alvoOlhar.y = random(-5, 5);
                tempoUltimoSalto = millis();
                
                setTimeout(() => {
                    alvoOlhar.x = 0;
                    alvoOlhar.y = 0;
                }, 200);
            }
            posicaoPupila.x = lerp(posicaoPupila.x, alvoOlhar.x, 0.2);
            posicaoPupila.y = lerp(posicaoPupila.y, alvoOlhar.y, 0.2);
            break;
    }
}

function desenharOlho() {
    let offsetX = (width - (colunas * tamanhoPixel)) / 2;
    let offsetY = (height - (linhas * tamanhoPixel)) / 2;
    
    let centroX = colunas / 2;
    let centroY = linhas / 2;
    
    let respiracao = sin(frameCount * 0.03) * estado.intensidadeRespiracao;
    let raioOlho = 12 + respiracao;
    
    for (let x = 0; x < colunas; x++) {
        for (let y = 0; y < linhas; y++) {
            let pixel = false;
            let alpha = 255;
            
            let dx = x - centroX;
            let dy = y - centroY;
            let distCentro = sqrt(dx * dx + dy * dy);
            let angulo = atan2(dy, dx);
            
            let raioComDeformacao = calcularDeformacao(angulo, raioOlho);
            
            let dentroDoOlho = verificarFormatoOlho(distCentro, dy, raioComDeformacao);
            
            if (dentroDoOlho && distCentro > raioComDeformacao - 1.5) {
                pixel = true;
                if (estaFalando) {
                    alpha = 255 - (pulsoLuz * 50);
                }
            }
            
            if (dentroDoOlho && distCentro < raioComDeformacao - 1.5) {
                pixel = true;
                alpha = 100;
            }
            
            if (dentroDoOlho) {
                let pixelPupila = desenharPupila(x, y, centroX, centroY, raioOlho);
                if (pixelPupila.ativo) {
                    pixel = true;
                    alpha = pixelPupila.alpha;
                }
            }

            if (pixel) {
                fill(estado.r, estado.g, estado.b, alpha);
                rect(
                    offsetX + x * tamanhoPixel,
                    offsetY + y * tamanhoPixel,
                    tamanhoPixel - 1,
                    tamanhoPixel - 1,
                    2
                );
            }
        }
    }
}

function verificarFormatoOlho(distCentro, dy, raioComDeformacao) {
    let formato = obterFormatoAtual();
    
    switch (formato) {
        case "meia_lua":
            return distCentro < raioComDeformacao && dy > -raioComDeformacao * 0.3;
        case "arregalado":
            return distCentro < raioComDeformacao * 1.2;
        case "levemente_arregalado": 
            return distCentro < raioComDeformacao * 1.08;
        case "erratico":
        case "distorcido_leve":
        case "circular":
        default:
            return distCentro < raioComDeformacao;
    }
}

function calcularDeformacao(angulo, raioBase) {
    let deformacao = 0;
    let formato = obterFormatoAtual();
    
    switch (formato) {
        case "erratico":
            deformacao = noise(
                cos(angulo) * 2 + frameCount * estado.velocidadeMovimento,
                sin(angulo) * 2 + frameCount * estado.velocidadeMovimento
            ) - 0.5;
            deformacao *= estado.deformacao * 10;
            break;
        
        case "distorcido_leve":
            deformacao = sin(angulo * 3 + frameCount * 0.02) * estado.deformacao * 2;
            break;
        
        case "circular":
        case "arregalado":
        case "meia_lua":
        default:
            deformacao = noise(cos(angulo) * 2, sin(angulo) * 2, frameCount * 0.01) - 0.5;
            deformacao *= estado.deformacao * 3;
            break;
    }
    
    return raioBase + deformacao;
}

function desenharPupila(x, y, centroX, centroY, raioOlho) {
    let resultado = { ativo: false, alpha: 255 };
    let comportamento = obterComportamentoAtual();
    
    if (comportamento === "espiral") {
        let dx = x - centroX;
        let dy = y - centroY;
        let dist = sqrt(dx * dx + dy * dy);
        let angulo = atan2(dy, dx);
        
        let raioPupilaMax = raioOlho * estado.tamanhoPupila;
        
        if (dist < raioPupilaMax && dist > 0.5) {
            let voltas = 2.5;
            let anguloCalculado = (dist / raioPupilaMax) * voltas * TWO_PI;
            anguloCalculado += anguloEspiral; 
            
            let anguloAtual = angulo < 0 ? angulo + TWO_PI : angulo;
            let anguloAlvo = anguloCalculado % TWO_PI;
            
            let dif = abs(anguloAtual - anguloAlvo);
            if (dif > PI) dif = TWO_PI - dif;
            
            if (dif < 0.5) {
                resultado.ativo = true;
                resultado.alpha = 240;
            }
        }
        
        if (dist < 1.5) {
            resultado.ativo = true;
            resultado.alpha = 255;
        }
        
    } else {
        let distPupila = dist(
            x, y,
            centroX + posicaoPupila.x,
            centroY + posicaoPupila.y
        );
        
        let raioPupila = raioOlho * estado.tamanhoPupila;
        
        if (estaFalando) {
            raioPupila *= (1 + pulsoLuz * 0.3);
        }
        
        if (distPupila < raioPupila) {
            resultado.ativo = true;
            resultado.alpha = 255;
        }
        
        if (distPupila < raioPupila * 0.35) {
            resultado.ativo = true;
            resultado.alpha = 180;
        }
    }
    
    return resultado;
}

function windowResized() {
    resizeCanvas(windowWidth, windowHeight);
    tamanhoPixel = min(width, height) / colunas;
}