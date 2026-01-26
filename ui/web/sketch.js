let colunas = 50;
let linhas = 50;
let tamanhoPixel;

let estado = {
    r: 0, g: 255, b: 0,
    velocidade: 0.02
};

let alvo = { ...estado };
let estaFalando = false;
let textoAtual = "AGUARDANDO...";

let tempoUltimaPiscada = 0;
let piscando = false;
let duracaoPiscada = 150;
let movimentoBoca = 0;
let tremor = 0;
let movimentoPupila = { x: 0, y: 0 };

const EXPRESSOES = {
    "neutro": {
        r: 0, g: 255, b: 0,
        olhoEsquerdo: { forma: "circulo", tamanho: 1.0, offsetY: 0 },
        olhoDireito: { forma: "circulo", tamanho: 0.95, offsetY: 0.2 },
        sobrancelhaEsq: { altura: -1, angulo: -3, comprimento: 5 },
        sobrancelhaDir: { altura: -0.9, angulo: 3, comprimento: 4.8 },
        boca: { tipo: "irregular", pontos: [0, 0.1, 0.2, 0.3, 0.3, 0.2, 0.1, 0] }
    },
    "feliz": {
        r: 0, g: 255, b: 200,
        olhoEsquerdo: { forma: "circulo", tamanho: 1.05, offsetY: 0 },
        olhoDireito: { forma: "circulo", tamanho: 1.0, offsetY: 0.15 },
        sobrancelhaEsq: { altura: -1.5, angulo: 8, comprimento: 5 },
        sobrancelhaDir: { altura: -1.4, angulo: 10, comprimento: 5 },
        boca: { tipo: "sorriso_simples", pontos: [0, 0.8, 1.5, 2.0, 2.0, 1.5, 0.8, 0] }
    },
    "irritado": {
        r: 255, g: 0, b: 0,
        olhoEsquerdo: { forma: "irritado", tamanho: 0.9, offsetY: 0 },
        olhoDireito: { forma: "irritado", tamanho: 0.88, offsetY: 0.3 },
        sobrancelhaEsq: { altura: -0.5, angulo: -20, comprimento: 5 },
        sobrancelhaDir: { altura: -0.4, angulo: -22, comprimento: 4.8 },
        boca: { tipo: "irregular", pontos: [0, -0.2, -0.3, -0.4, -0.4, -0.3, -0.2, 0] }
    },
    "confuso": {
        r: 255, g: 150, b: 0,
        olhoEsquerdo: { forma: "circulo", tamanho: 0.8, offsetY: 0 },
        olhoDireito: { forma: "circulo", tamanho: 1.15, offsetY: -0.3 },
        sobrancelhaEsq: { altura: -1, angulo: 3, comprimento: 4.5 },
        sobrancelhaDir: { altura: -2.8, angulo: 20, comprimento: 5 },
        boca: { tipo: "irregular", pontos: [0, 0.05, -0.05, 0.1, 0, -0.1, 0.05, 0] }
    },
    "desconfiado": {
        r: 255, g: 255, b: 0,
        olhoEsquerdo: { forma: "semicirculo", tamanho: 0.8, offsetY: 0 },
        olhoDireito: { forma: "semicirculo", tamanho: 0.77, offsetY: 0.2 },
        sobrancelhaEsq: { altura: -0.8, angulo: -8, comprimento: 5 },
        sobrancelhaDir: { altura: -0.7, angulo: -10, comprimento: 4.8 },
        boca: { tipo: "irregular", pontos: [0, 0, 0, 0, 0, 0, 0, 0] }
    },
    "arrogante": {
        r: 200, g: 0, b: 255,
        olhoEsquerdo: { forma: "semicirculo", tamanho: 0.9, offsetY: 0 },
        olhoDireito: { forma: "semicirculo", tamanho: 0.87, offsetY: 0.15 },
        sobrancelhaEsq: { altura: -2, angulo: 12, comprimento: 5 },
        sobrancelhaDir: { altura: -1.9, angulo: 14, comprimento: 5 },
        boca: { tipo: "irregular", pontos: [0, 0.2, 0.5, 0.9, 1.2, 0.6, 0.3, 0] }
    },
    "sarcasmo_tedio": {
        r: 100, g: 150, b: 255,
        olhoEsquerdo: { forma: "entediado", tamanho: 0.7, offsetY: 0 },
        olhoDireito: { forma: "entediado", tamanho: 0.68, offsetY: 0.15 },
        sobrancelhaEsq: { altura: 0.8, angulo: -5, comprimento: 5 },
        sobrancelhaDir: { altura: 1, angulo: -3, comprimento: 4.8 },
        boca: { tipo: "irregular", pontos: [0, 0, -0.05, 0, 0.05, 0, 0, 0] }
    },
    "ouvindo": {
        r: 0, g: 180, b: 255,
        olhoEsquerdo: { forma: "circulo", tamanho: 1.25, offsetY: 0 },
        olhoDireito: { forma: "circulo", tamanho: 1.22, offsetY: -0.2 },
        sobrancelhaEsq: { altura: -2, angulo: 10, comprimento: 5 },
        sobrancelhaDir: { altura: -1.9, angulo: 12, comprimento: 5 },
        boca: { tipo: "irregular", pontos: [0, 0.2, 0.4, 0.5, 0.5, 0.4, 0.2, 0] }
    }
};

let expressaoAtual = EXPRESSOES["neutro"];
let expressaoAlvo = EXPRESSOES["neutro"];

eel.expose(jsAtualizarRosto);
function jsAtualizarRosto(emocao, falando) {
    console.log(`[UI] Emoção: ${emocao} | Falando: ${falando}`);
    
    estaFalando = falando;
    expressaoAlvo = EXPRESSOES[emocao] || EXPRESSOES["neutro"];
    
    alvo.r = expressaoAlvo.r;
    alvo.g = expressaoAlvo.g;
    alvo.b = expressaoAlvo.b;
}

eel.expose(jsAtualizarTexto);
function jsAtualizarTexto(texto) {
    console.log(`[UI] Texto: ${texto}`);
    textoAtual = texto;
}

function setup() {
    createCanvas(windowWidth, windowHeight);
    noStroke();
    tamanhoPixel = min(width, height) / colunas;
}

function draw() {
    background(10);
    
    let suavidade = 0.1;
    estado.r = lerp(estado.r, alvo.r, suavidade);
    estado.g = lerp(estado.g, alvo.g, suavidade);
    estado.b = lerp(estado.b, alvo.b, suavidade);
    
    expressaoAtual = interpolarExpressao(expressaoAtual, expressaoAlvo, suavidade);
    
    if (millis() - tempoUltimaPiscada > random(3000, 6000) && !piscando) {
        piscando = true;
        tempoUltimaPiscada = millis();
    }
    if (piscando && millis() - tempoUltimaPiscada > duracaoPiscada) {
        piscando = false;
    }
    
    if (estaFalando) {
        movimentoBoca = sin(frameCount * 0.4) * 0.3;
        tremor = sin(frameCount * 0.3) * 0.1;
    } else {
        movimentoBoca = lerp(movimentoBoca, 0, 0.15);
        tremor = lerp(tremor, 0, 0.15);
    }
    

    movimentoPupila.x = sin(frameCount * 0.015) * 0.6;
    movimentoPupila.y = cos(frameCount * 0.02) * 0.4;
    
    let offsetX = (width - (colunas * tamanhoPixel)) / 2;
    let offsetY = (height - (linhas * tamanhoPixel)) / 2;
    
    // Posições base
    let olhoEsqX = colunas * 0.35;
    let olhoDirX = colunas * 0.65;
    let olhosY = linhas * 0.38;
    let bocaY = linhas * 0.68;

    for (let x = 0; x < colunas; x++) {
        for (let y = 0; y < linhas; y++) {
            
            let pixel = false;
            let alpha = 255;
            
            // OLHO ESQUERDO
            if (desenharOlho(x, y, olhoEsqX, olhosY + expressaoAtual.olhoEsquerdo.offsetY + tremor, expressaoAtual.olhoEsquerdo, piscando)) {
                pixel = true;
            }
            
            // OLHO DIREITO  
            if (desenharOlho(x, y, olhoDirX, olhosY + expressaoAtual.olhoDireito.offsetY + tremor, expressaoAtual.olhoDireito, piscando)) {
                pixel = true;
            }
            
            // SOBRANCELHA ESQUERDA
            if (desenharSobrancelhaAngulada(x, y, olhoEsqX, olhosY + expressaoAtual.olhoEsquerdo.offsetY, expressaoAtual.sobrancelhaEsq)) {
                pixel = true;
            }
            
            // SOBRANCELHA DIREITA
            if (desenharSobrancelhaAngulada(x, y, olhoDirX, olhosY + expressaoAtual.olhoDireito.offsetY, expressaoAtual.sobrancelhaDir)) {
                pixel = true;
            }
            
            // BOCA
            if (desenharBoca(x, y, colunas / 2, bocaY + movimentoBoca, expressaoAtual.boca)) {
                pixel = true;
            }
            
            // Pupilas
            if (!piscando) {
                let distPupilaEsq = dist(x, y, olhoEsqX + movimentoPupila.x, olhosY + expressaoAtual.olhoEsquerdo.offsetY + movimentoPupila.y);
                if (distPupilaEsq < 1.0) {
                    pixel = true;
                    alpha = 180;
                }
                
                let distPupilaDir = dist(x, y, olhoDirX + movimentoPupila.x * 0.95, olhosY + expressaoAtual.olhoDireito.offsetY + movimentoPupila.y * 1.05);
                if (distPupilaDir < 0.95) {
                    pixel = true;
                    alpha = 180;
                }
            }
            
            // Desenhar pixel
            if (pixel) {
                fill(estado.r, estado.g, estado.b, alpha);
                rect(
                    offsetX + x * tamanhoPixel,
                    offsetY + y * tamanhoPixel,
                    tamanhoPixel - 1,
                    tamanhoPixel - 1,
                    1
                );
            }
        }
    }
    
    // Texto
    push();
    fill(0, 0, 0, 200);
    noStroke();
    rect(0, height - 60, width, 60);
    
    fill(estado.r, estado.g, estado.b);
    textSize(18);
    textAlign(CENTER, CENTER);
    textFont('Courier New');
    textStyle(BOLD);
    text(textoAtual, width / 2, height - 30);
    pop();
}

function desenharOlho(x, y, centroX, centroY, config, piscando) {
    let raio = 4 * config.tamanho;
    let distCentro = dist(x, y, centroX, centroY);
    
    if (piscando) {
        return abs(y - centroY) < 0.7 && abs(x - centroX) < raio;
    }
    
    switch (config.forma) {
        case "circulo":
            return distCentro < raio;
        
        case "semicirculo":
            return distCentro < raio && y >= centroY - 0.5;
        
        case "irritado":
            let inclinacao = (x - centroX) * 0.35;
            return distCentro < raio && abs(y - (centroY + inclinacao)) < raio * 0.7;
        
        case "entediado":
            return distCentro < raio && y >= centroY;
        
        default:
            return distCentro < raio;
    }
}

function desenharSobrancelhaAngulada(x, y, centroX, centroY, config) {
    let yBase = centroY + config.altura - 7;
    let distX = x - centroX;
    let comprimento = config.comprimento;
    
    if (abs(distX) > comprimento) return false;
    
    let angulo = config.angulo * (PI / 180);
    let yAngulo = distX * tan(angulo);
    let yEsperado = yBase + yAngulo;
    
    return abs(y - yEsperado) < 0.55 && abs(distX) < comprimento;
}

function desenharBoca(x, y, centroX, centroY, config) {
    let largura = 18;
    let distX = x - centroX;
    
    if (abs(distX) > largura / 2) return false;
    
    let indice = map(abs(distX), 0, largura / 2, 0, config.pontos.length - 1);
    let i1 = floor(indice);
    let i2 = min(i1 + 1, config.pontos.length - 1);
    let frac = indice - i1;
    
    let altura = lerp(config.pontos[i1], config.pontos[i2], frac);
    let yEsperado = centroY + altura;

    if (estaFalando) {
        yEsperado += sin(frameCount * 0.2 + distX * 0.5) * 0.15;
    }
    
    return abs(y - yEsperado) < 0.75;
}

function interpolarExpressao(atual, alvo, t) {
    return {
        olhoEsquerdo: {
            forma: alvo.olhoEsquerdo.forma,
            tamanho: lerp(atual.olhoEsquerdo.tamanho, alvo.olhoEsquerdo.tamanho, t),
            offsetY: lerp(atual.olhoEsquerdo.offsetY, alvo.olhoEsquerdo.offsetY, t)
        },
        olhoDireito: {
            forma: alvo.olhoDireito.forma,
            tamanho: lerp(atual.olhoDireito.tamanho, alvo.olhoDireito.tamanho, t),
            offsetY: lerp(atual.olhoDireito.offsetY, alvo.olhoDireito.offsetY, t)
        },
        sobrancelhaEsq: {
            altura: lerp(atual.sobrancelhaEsq.altura, alvo.sobrancelhaEsq.altura, t),
            angulo: lerp(atual.sobrancelhaEsq.angulo, alvo.sobrancelhaEsq.angulo, t),
            comprimento: lerp(atual.sobrancelhaEsq.comprimento, alvo.sobrancelhaEsq.comprimento, t)
        },
        sobrancelhaDir: {
            altura: lerp(atual.sobrancelhaDir.altura, alvo.sobrancelhaDir.altura, t),
            angulo: lerp(atual.sobrancelhaDir.angulo, alvo.sobrancelhaDir.angulo, t),
            comprimento: lerp(atual.sobrancelhaDir.comprimento, alvo.sobrancelhaDir.comprimento, t)
        },
        boca: {
            tipo: alvo.boca.tipo,
            pontos: atual.boca.pontos.map((p, i) => lerp(p, alvo.boca.pontos[i], t))
        }
    };
}

function windowResized() {
    resizeCanvas(windowWidth, windowHeight);
    tamanhoPixel = min(width, height) / colunas;
}