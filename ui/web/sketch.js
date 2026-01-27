
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
let piscando = false;
let tempoUltimaPiscada = 0;
let duracaoPiscada = 200;

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
        tamanhoPupila: 0.35,
        deformacao: 0.15,
        velocidadeMovimento: 0.02,
        intensidadeRespiracao: 0.06,
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
        ondasSonoras: true
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
    alvo.tamanhoPupila = expressaoAlvo.tamanhoPupila;
    alvo.deformacao = expressaoAlvo.deformacao;
    alvo.velocidadeMovimento = expressaoAlvo.velocidadeMovimento;
    alvo.intensidadeRespiracao = expressaoAlvo.intensidadeRespiracao;
}

eel.expose(jsAtualizarOlhar);
function jsAtualizarOlhar(x, y, encontrouRosto) {
    console.log(`[VISION] Rosto: ${encontrouRosto} | X: ${x.toFixed(2)} | Y: ${y.toFixed(2)}`);
    
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
    
    expressaoAtual = interpolarExpressao(expressaoAtual, expressaoAlvo, suavidade);
    
    if (millis() - tempoUltimaPiscada > random(2500, 5000) && !piscando) {
        piscando = true;
        tempoUltimaPiscada = millis();
    }
    if (piscando && millis() - tempoUltimaPiscada > duracaoPiscada) {
        piscando = false;
    }

    atualizarPosicaoPupila();
    
    if (expressaoAtual.comportamentoPupila === "espiral") {
        anguloEspiral += 0.1;
    }
    
    if (estaFalando) {
        pulsoLuz = sin(frameCount * 0.3) * 0.5 + 0.5;
    } else {
        pulsoLuz = lerp(pulsoLuz, 0, 0.1);
    }
    
    // Desenhar o olho
    desenharOlho();
    
}


function atualizarPosicaoPupila() {
    if (rastreamentoCamera.ativo && millis() - rastreamentoCamera.ultimoUpdate < 2000) {
        posicaoPupila.x = lerp(posicaoPupila.x, rastreamentoCamera.x, 0.15);
        posicaoPupila.y = lerp(posicaoPupila.y, rastreamentoCamera.y, 0.15);
        return;
    }

    switch (expressaoAtual.comportamentoPupila) {
        case "saltos_rapidos":
            // Neutro
            if (millis() - tempoUltimoSalto > random(800, 1500)) {
                alvoOlhar.x = random(-4, 4);
                alvoOlhar.y = random(-4, 4);
                tempoUltimoSalto = millis();
            }
            posicaoPupila.x = lerp(posicaoPupila.x, alvoOlhar.x, 0.08);
            posicaoPupila.y = lerp(posicaoPupila.y, alvoOlhar.y, 0.08);
            break;
        
        case "centralizado":
            // Fica no centro
            posicaoPupila.x = lerp(posicaoPupila.x, 0, 0.1);
            posicaoPupila.y = lerp(posicaoPupila.y, 0, 0.1);
            break;
        
        case "espiral":
            // Confuso
            posicaoPupila.x = 0;
            posicaoPupila.y = 0;
            break;
        
        case "observando_rapido":
            // Desconfiado
            if (millis() - tempoUltimoSalto > random(150, 400)) {
                alvoOlhar.x = random(-5, 5);
                alvoOlhar.y = random(-5, 5);
                tempoUltimoSalto = millis();
            }
            posicaoPupila.x = lerp(posicaoPupila.x, alvoOlhar.x, 0.25);
            posicaoPupila.y = lerp(posicaoPupila.y, alvoOlhar.y, 0.25);
            break;
        
        case "cantos_lentos":
            // Arrogante
            alvoOlhar.x = sin(frameCount * 0.02) * 3;
            alvoOlhar.y = cos(frameCount * 0.015) * 3;
            posicaoPupila.x = lerp(posicaoPupila.x, alvoOlhar.x, 0.03);
            posicaoPupila.y = lerp(posicaoPupila.y, alvoOlhar.y, 0.03);
            break;
        
        case "centro_com_saltos":
            // Feliz
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
    
    // Respiração
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
            
            // Verificar formato do olho
            let dentroDoOlho = verificarFormatoOlho(distCentro, dy, raioComDeformacao);
            
            // Borda do olho 
            if (dentroDoOlho && distCentro > raioComDeformacao - 1.5) {
                pixel = true;
                if (estaFalando) {
                    alpha = 255 - (pulsoLuz * 50);
                }
            }
            
            // Interior do olho
            if (dentroDoOlho && distCentro < raioComDeformacao - 1.5) {
                pixel = true;
                alpha = 100;
            }
            
            // Pupila
            if (!piscando && dentroDoOlho) {
                let pixelPupila = desenharPupila(x, y, centroX, centroY, raioOlho);
                if (pixelPupila.ativo) {
                    pixel = true;
                    alpha = pixelPupila.alpha;
                }
            }
            
            // Ondas sonoras 
            if (expressaoAtual.ondasSonoras && !pixel && !estaFalando) {
                let ondas = desenharOndasSonoras(distCentro, raioComDeformacao);
                if (ondas) {
                    pixel = true;
                    alpha = ondas;
                }
            }
            
            // Piscada
            if (piscando) {
                let progressoPiscada = (millis() - tempoUltimaPiscada) / duracaoPiscada;
                let fechamento = sin(progressoPiscada * PI) * raioOlho * 0.8;
                if (abs(dy) > fechamento) {
                    pixel = false;
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
    switch (expressaoAtual.formatoOlho) {
        case "meia_lua":
            return distCentro < raioComDeformacao && dy > -raioComDeformacao * 0.3;
        case "arregalado":
            return distCentro < raioComDeformacao * 1.2;
        case "erratico":
        case "distorcido_leve":
        case "circular":
        default:
            return distCentro < raioComDeformacao;
    }
}

function calcularDeformacao(angulo, raioBase) {
    let deformacao = 0;
    
    switch (expressaoAtual.formatoOlho) {
        case "erratico":
            // Irritado
            deformacao = noise(
                cos(angulo) * 2 + frameCount * estado.velocidadeMovimento,
                sin(angulo) * 2 + frameCount * estado.velocidadeMovimento
            ) - 0.5;
            deformacao *= estado.deformacao * 10;
            break;
        
        case "distorcido_leve":
            // Arrogante
            deformacao = sin(angulo * 3 + frameCount * 0.02) * estado.deformacao * 2;
            break;
        
        case "circular":
        case "arregalado":
        case "meia_lua":
        default:
            // Deformação orgânica mínima
            deformacao = noise(cos(angulo) * 2, sin(angulo) * 2, frameCount * 0.01) - 0.5;
            deformacao *= estado.deformacao * 3;
            break;
    }
    
    return raioBase + deformacao;
}

function desenharPupila(x, y, centroX, centroY, raioOlho) {
    let resultado = { ativo: false, alpha: 255 };
    
    if (expressaoAtual.comportamentoPupila === "espiral") {
        // Pupila em espiral
        let dx = x - centroX;
        let dy = y - centroY;
        let dist = sqrt(dx * dx + dy * dy);
        let angulo = atan2(dy, dx);
        
        let espiral = (dist * 0.5 + anguloEspiral) % (PI * 2);
        let larguraEspiral = 1.2;
        let anguloNormalizado = (angulo + PI) % (PI * 2);
        let diferencaAngulo = abs(anguloNormalizado - espiral);
        
        if (diferencaAngulo < larguraEspiral || (PI * 2 - diferencaAngulo) < larguraEspiral) {
            if (dist < raioOlho * estado.tamanhoPupila) {
                resultado.ativo = true;
                resultado.alpha = 255;
            }
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

function desenharOndasSonoras(distCentro, raioOlho) {
    let numOndas = 3;
    let espacamento = 3;
    
    for (let i = 0; i < numOndas; i++) {
        let raioOnda = raioOlho + espacamento * (i + 1) + (frameCount * 0.15) % (espacamento * numOndas);
        
        if (abs(distCentro - raioOnda) < 0.8) {
            return map(i, 0, numOndas, 150, 50);
        }
    }
    
    return false;
}


function interpolarExpressao(atual, alvo, t) {
    return {
        comportamentoPupila: alvo.comportamentoPupila,
        formatoOlho: alvo.formatoOlho,
        ondasSonoras: alvo.ondasSonoras || false
    };
}

function windowResized() {
    resizeCanvas(windowWidth, windowHeight);
    tamanhoPixel = min(width, height) / colunas;
}