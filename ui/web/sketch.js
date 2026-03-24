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

let painelAberto = false;
let uptimeSegundos = 0;

const LARGURA_PAINEL = 310;

const EXPRESSOES = {
    "neutro": {
        r: 0, g: 255, b: 0,
        tamanhoPupila: 0.3,
        deformacao: 0.05,
        velocidadeMovimento: 0.01,
        intensidadeRespiracao: 0.03,
        comportamentoPupila: "saltos_rapidos",
        formatoOlho: "circular",
        brilhoMultiplicador: 1.0
    },
    "sarcasmo_tedio": {
        r: 100, g: 150, b: 255,
        tamanhoPupila: 0.4,
        deformacao: 0.08,
        velocidadeMovimento: 0.01,
        intensidadeRespiracao: 0.02,
        comportamentoPupila: "centralizado",
        formatoOlho: "meia_lua",
        brilhoMultiplicador: 1.0
    },
    "irritado": {
        r: 255, g: 0, b: 0,
        tamanhoPupila: 0.15,
        deformacao: 0.5,
        velocidadeMovimento: 0.1,
        intensidadeRespiracao: 0.02,
        comportamentoPupila: "centralizado",
        formatoOlho: "erratico",
        brilhoMultiplicador: 1.0
    },
    "confuso": {
        r: 255, g: 150, b: 0,
        tamanhoPupila: 0.38,
        deformacao: 0.12,
        velocidadeMovimento: 0.02,
        intensidadeRespiracao: 0.05,
        comportamentoPupila: "espiral",
        formatoOlho: "arregalado",
        brilhoMultiplicador: 1.0
    },
    "desconfiado": {
        r: 255, g: 255, b: 0,
        tamanhoPupila: 0.2,
        deformacao: 0.1,
        velocidadeMovimento: 0.02,
        intensidadeRespiracao: 0.03,
        comportamentoPupila: "observando_rapido",
        formatoOlho: "circular",
        brilhoMultiplicador: 1.0
    },
    "arrogante": {
        r: 200, g: 0, b: 255,
        tamanhoPupila: 0.28,
        deformacao: 0.15,
        velocidadeMovimento: 0.02,
        intensidadeRespiracao: 0.04,
        comportamentoPupila: "cantos_lentos",
        formatoOlho: "distorcido_leve",
        brilhoMultiplicador: 1.0
    },
    "feliz": {
        r: 0, g: 255, b: 200,
        tamanhoPupila: 0.35,
        deformacao: 0.12,
        velocidadeMovimento: 0.03,
        intensidadeRespiracao: 0.05,
        comportamentoPupila: "centro_com_saltos",
        formatoOlho: "circular",
        brilhoMultiplicador: 1.0
    },
    "ouvindo": {
        r: 0, g: 180, b: 255,
        tamanhoPupila: 0.5,
        deformacao: 0.08,
        velocidadeMovimento: 0.02,
        intensidadeRespiracao: 0.04,
        comportamentoPupila: "centralizado",
        formatoOlho: "circular",
        brilhoMultiplicador: 1.0
    },
    "dormindo": {
        r: 0, g: 60, b: 0,
        tamanhoPupila: 0.15,
        deformacao: 0.04,
        velocidadeMovimento: 0.003,
        intensidadeRespiracao: 0.008,
        comportamentoPupila: "centralizado",
        formatoOlho: "meia_lua",
        brilhoMultiplicador: 0.18
    }
};

let expressaoAtual = EXPRESSOES["neutro"];
let expressaoAlvo = EXPRESSOES["neutro"];
let progressoTransicao = 1.0;

let _framesCalibracao = 0;
let _bgAlpha = 0;

const BOOT = {
    FASE_SCAN: 0,
    FASE_OLHO: 1,
    FASE_COMPLETO: 2
};

let boot = {
    ativo: true,
    fase: BOOT.FASE_SCAN,
    frame: 0,
    scanY: 0,
    pixelsOlho: [],
};

function _api() {
    return window.pywebview && window.pywebview.api ? window.pywebview.api : null;
}

function jsAtualizarRosto(emocao, falando) {
    estaFalando = falando;
    let novaExpressao = EXPRESSOES[emocao] || EXPRESSOES["neutro"];

    if (novaExpressao !== expressaoAlvo) {
        expressaoAtual = expressaoAlvo;
        progressoTransicao = 0.0;
    }

    expressaoAlvo = novaExpressao;
    alvo.r = expressaoAlvo.r;
    alvo.g = expressaoAlvo.g;
    alvo.b = expressaoAlvo.b;
    alvo.tamanhoPupila = expressaoAlvo.tamanhoPupila;
    alvo.deformacao = expressaoAlvo.deformacao;
    alvo.velocidadeMovimento = expressaoAlvo.velocidadeMovimento;
    alvo.intensidadeRespiracao = expressaoAlvo.intensidadeRespiracao;

    let el = document.getElementById('eye-emocao');
    if (el) el.textContent = 'ESTADO: ' + emocao.toUpperCase();
}

function jsAtualizarOlhar(x, y, encontrouRosto) {
    rastreamentoCamera.ativo = encontrouRosto;
    rastreamentoCamera.x = x;
    rastreamentoCamera.y = y;
    rastreamentoCamera.ultimoUpdate = millis();
}

function jsAbrirConfig() {
    if (painelAberto) return;
    painelAberto = true;

    let api = _api();
    if (api) {
        api.maximizar_janela();
        api.obter_settings().then(function(cfg) {
            sincronizarUI(cfg);
        });
    }

    document.getElementById('btn-fechar').classList.add('hidden');
    document.getElementById('eye-overlay').classList.add('visible');

    let painel = document.getElementById('painel-config');
    painel.style.display = 'flex';
    painel.style.opacity = '0';
    painel.style.transform = 'translateX(-20px)';
    painel.style.transition = 'opacity 0.3s ease, transform 0.3s ease';

    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            painel.style.opacity = '1';
            painel.style.transform = 'translateX(0)';
            let flash = document.getElementById('boot-flash');
            flash.classList.remove('active');
            void flash.offsetWidth;
            flash.classList.add('active');
        });
    });

    iniciarRelogio();
    iniciarUptime();
    atualizarStatusMsg("MÓDULO DE CONFIGURAÇÃO CARREGADO");
}

function fecharConfig() {
    let painel = document.getElementById('painel-config');
    painel.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
    painel.style.opacity = '0';
    painel.style.transform = 'translateX(-20px)';
    setTimeout(() => {
        painel.style.display = 'none';
        painelAberto = false;
        document.getElementById('btn-fechar').classList.remove('hidden');
        document.getElementById('eye-overlay').classList.remove('visible');
        let api = _api();
        if (api) api.restaurar_janela();
    }, 260);
    let api = _api();
    if (api) api.fechar_configuracoes();
}

function updateFill(slider, min, max) {
    let pct = ((slider.value - min) / (max - min)) * 100;
    slider.style.setProperty('--fill', pct.toFixed(1) + '%');
}

function toggleConfig(chave, el) {
    let ativo = !el.classList.contains('active');
    el.classList.toggle('active', ativo);
    document.getElementById('lbl-' + chave).textContent = ativo ? 'ATIVO' : 'INATIVO';
    let api = _api();
    if (api) api.atualizar_setting(chave, ativo);
    atualizarStatusMsg("CONFIG ATUALIZADO: " + chave.toUpperCase());
}

function sliderConfig(chave, valor, labelId, fmt) {
    document.getElementById(labelId).textContent = fmt(valor);
    let api = _api();
    if (api) api.atualizar_setting(chave, valor);
}

function updateConfig(chave, valor) {
    let api = _api();
    if (api) api.atualizar_setting(chave, valor);
    atualizarStatusMsg("CONFIG ATUALIZADO: " + chave.toUpperCase());
}

function sincronizarUI(cfg) {
    if (!cfg) return;

    sincronizarToggle('vad_ativo', cfg.vad_ativo !== false);
    sincronizarToggle('camera_ativa', cfg.camera_ativa !== false);
    sincronizarToggle('modo_debug', cfg.modo_debug === true);
    sincronizarToggle('comportamento_espontaneo', cfg.comportamento_espontaneo !== false);

    sincronizarSlider('vad_threshold', cfg.vad_threshold, 'val-vad_threshold',
        v => parseFloat(v).toFixed(2), v => Math.round(v * 100));
    sincronizarSlider('vad_energia', cfg.vad_energia, 'val-vad_energia',
        v => parseFloat(v).toFixed(2), v => Math.round(v * 100));
    sincronizarSlider('vad_consecutivo', cfg.vad_consecutivo, 'val-vad_consecutivo',
        v => v, v => v);
    sincronizarSlider('energia_microfone', cfg.energia_microfone, 'val-energia_microfone',
        v => v, v => v);
    sincronizarSlider('modo_ambient_timeout_min', cfg.modo_ambient_timeout_min, 'val-ambient_timeout',
        v => v + 'min', v => v);
    sincronizarSlider('dormindo_timeout_min', cfg.dormindo_timeout_min, 'val-dormindo_timeout',
        v => v + 'min', v => v);
    sincronizarSlider('espontaneo_cooldown_min', cfg.espontaneo_cooldown_min, 'val-espontaneo_cooldown',
        v => v + 'min', v => v);
    sincronizarSlider('espontaneo_limite_diario', cfg.espontaneo_limite_diario, 'val-espontaneo_limite',
        v => v + 'x', v => v);

    let sel = document.getElementById('select-modelo');
    if (sel && cfg.modelo) sel.value = cfg.modelo;

    let selWm = document.getElementById('select-whisper_modelo');
    if (selWm && cfg.whisper_modelo) selWm.value = cfg.whisper_modelo;

    let selWd = document.getElementById('select-whisper_device');
    if (selWd && cfg.whisper_device) selWd.value = cfg.whisper_device;
}

function sincronizarToggle(chave, ativo) {
    let el = document.getElementById('toggle-' + chave);
    let lbl = document.getElementById('lbl-' + chave);
    if (!el || !lbl) return;
    el.classList.toggle('active', ativo);
    lbl.textContent = ativo ? 'ATIVO' : 'INATIVO';
}

function sincronizarSlider(chave, valor, labelId, fmt, toSlider) {
    let slider = document.getElementById('slider-' + chave);
    let label = document.getElementById(labelId);
    if (!slider || !label || valor === undefined) return;
    slider.value = toSlider(valor);
    label.textContent = fmt(valor);
}

let _clockInterval = null;
let _uptimeInterval = null;

function iniciarRelogio() {
    if (_clockInterval) return;
    _clockInterval = setInterval(() => {
        let agora = new Date();
        let h = String(agora.getHours()).padStart(2, '0');
        let m = String(agora.getMinutes()).padStart(2, '0');
        let s = String(agora.getSeconds()).padStart(2, '0');
        let el = document.getElementById('eva-clock');
        if (el) el.textContent = h + ':' + m + ':' + s;
    }, 1000);
}

function iniciarUptime() {
    if (_uptimeInterval) return;
    _uptimeInterval = setInterval(() => {
        uptimeSegundos++;
        let h = String(Math.floor(uptimeSegundos / 3600)).padStart(2, '0');
        let m = String(Math.floor((uptimeSegundos % 3600) / 60)).padStart(2, '0');
        let s = String(uptimeSegundos % 60).padStart(2, '0');
        let el = document.getElementById('d-uptime');
        if (el) el.textContent = h + ':' + m + ':' + s;
    }, 1000);
}

function atualizarStatusMsg(msg) {
    let el = document.getElementById('eva-status-msg');
    if (!el) return;
    el.textContent = msg;
    el.classList.add('flash');
    setTimeout(() => {
        el.classList.remove('flash');
        el.textContent = 'SISTEMA OPERACIONAL NOMINAL';
    }, 2500);
}

function _iniciarBootAnimation() {
    boot.ativo = true;
    boot.fase = BOOT.FASE_SCAN;
    boot.frame = 0;
    boot.scanY = 0;
    boot.pixelsOlho = [];
    _bgAlpha = 0;

    let centroX = colunas / 2;
    let centroY = linhas / 2;
    let raioMax = 18;

    let pixels = [];
    for (let x = 0; x < colunas; x++) {
        for (let y = 0; y < linhas; y++) {
            let dx = x - centroX;
            let dy = y - centroY;
            let d = sqrt(dx * dx + dy * dy);
            if (d < raioMax) pixels.push({ x, y, dist: d });
        }
    }
    pixels.sort((a, b) => a.dist - b.dist);

    let grupos = [];
    let i = 0;
    while (i < pixels.length) {
        let tam = floor(random(3, 9));
        grupos.push(pixels.slice(i, i + tam));
        i += tam;
    }
    boot.pixelsOlho = grupos;
}

function _desenharBoot() {
    clear();
    boot.frame++;

    if (boot.fase === BOOT.FASE_SCAN) {
        boot.scanY += 5;

        noStroke();
        fill(0, 0, 0, map(boot.scanY, 0, height, 0, 180));
        rect(0, 0, width, boot.scanY - 40);

        for (let i = 0; i < 40; i++) {
            let a = map(i, 0, 40, 0, 80);
            fill(0, floor(a * 0.15), 0, a);
            rect(0, boot.scanY - 40 + i, width, 1);
        }

        fill(0, 220, 65, 100);
        rect(0, boot.scanY - 1, width, 2);
        fill(0, 255, 65, 35);
        rect(0, boot.scanY - 6, width, 6);

        textFont('Courier New');
        textSize(8);
        textAlign(LEFT);
        fill(0, 255, 65, 14);
        for (let row = 0; row < boot.scanY; row += 12) {
            if (noise(row * 0.08, boot.frame * 0.04) > 0.65) {
                let cols = floor(width / 22);
                for (let c = 0; c < cols; c++) {
                    text(hex(floor(random(65536)), 4), c * 22 + 4, row);
                }
            }
        }

        if (boot.scanY >= height + 60) {
            boot.fase = BOOT.FASE_OLHO;
            boot.frame = 0;
        }

    } else if (boot.fase === BOOT.FASE_OLHO) {

        _bgAlpha = lerp(_bgAlpha, 255, 0.025);
        fill(0, 0, 0, _bgAlpha);
        rect(0, 0, width, height);

        let total = boot.pixelsOlho.length;
        let gruposVisiveis = floor(map(boot.frame, 0, 90, 0, total));
        gruposVisiveis = constrain(gruposVisiveis, 0, total);

        let { px, ox, oy } = calcularAreaOlho();
        let centroX = colunas / 2;
        let centroY = linhas / 2;
        let raioOlho = 12;

        noStroke();
        for (let g = 0; g < gruposVisiveis; g++) {
            for (let p of boot.pixelsOlho[g]) {
                let dx = p.x - centroX;
                let dy = p.y - centroY;
                let ang = atan2(dy, dx);
                let raioD = calcularDeformacao(ang, raioOlho);
                if (!verificarFormatoOlho(p.dist, dy, raioD)) continue;

                let n = noise(p.x * 0.3, p.y * 0.3, boot.frame * 0.12);
                let alpha = map(n, 0.3, 0.7, 80, 255);
                let glitch = n > 0.78;
                fill(glitch ? 255 : 0, glitch ? 60 : floor(map(alpha, 80, 255, 120, 255)), 0, alpha);
                rect(ox + p.x * px + random(-0.8, 0.8), oy + p.y * px + random(-0.4, 0.4), px - 1, px - 1, 2);
            }
        }

        if (gruposVisiveis >= total && boot.frame > 90) {
            boot.fase = BOOT.FASE_COMPLETO;
            boot.ativo = false;

            setTimeout(function() {
                let api = _api();
                if (api) {
                    api.ui_pronta();
                } else {
                    let tentativas = 0;
                    let intervalo = setInterval(() => {
                        tentativas++;
                        let a = _api();
                        if (a) {
                            a.ui_pronta();
                            clearInterval(intervalo);
                        } else if (tentativas > 20) {
                            clearInterval(intervalo);
                        }
                    }, 200);
                }
            }, 300);
        }
    }
}

function setup() {
    createCanvas(windowWidth, windowHeight);
    noStroke();
    tamanhoPixel = min(width, height) / colunas;
    console.log("[UI] Canvas inicializado");
    _iniciarBootAnimation();
}

function draw() {
    if (_framesCalibracao < 30) {
        _framesCalibracao++;
        if (windowWidth !== width || windowHeight !== height) {
            resizeCanvas(windowWidth, windowHeight);
            tamanhoPixel = min(width, height) / colunas;
        }
    }

    if (boot.ativo) {
        _desenharBoot();
        return;
    }

    _bgAlpha = lerp(_bgAlpha, 255, 0.08);
    background(10, 10, 10, _bgAlpha);

    let brilho = expressaoAlvo.brilhoMultiplicador !== undefined ? expressaoAlvo.brilhoMultiplicador : 1.0;
    let suavidade = 0.08;
    estado.r = lerp(estado.r, alvo.r * brilho, suavidade);
    estado.g = lerp(estado.g, alvo.g * brilho, suavidade);
    estado.b = lerp(estado.b, alvo.b * brilho, suavidade);
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
    if (t < 0.5) return expressaoAtual.comportamentoPupila;
    return expressaoAlvo.comportamentoPupila;
}

function obterFormatoAtual() {
    let t = easeInOutCubic(progressoTransicao);
    if (t < 0.5) return expressaoAtual.formatoOlho;
    return expressaoAlvo.formatoOlho;
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
                setTimeout(() => { alvoOlhar.x = 0; alvoOlhar.y = 0; }, 200);
            }
            posicaoPupila.x = lerp(posicaoPupila.x, alvoOlhar.x, 0.2);
            posicaoPupila.y = lerp(posicaoPupila.y, alvoOlhar.y, 0.2);
            break;
    }
}

function calcularAreaOlho() {
    if (painelAberto) {
        let disponivelW = LARGURA_PAINEL;
        let disponivel = min(disponivelW, height);
        let px = disponivel / colunas;
        let ox = width - disponivelW / 2 - (colunas * px) / 2;
        let oy = (height - linhas * px) / 2;
        return { px, ox, oy };
    }
    let px = min(width, height) / colunas;
    let ox = (width - colunas * px) / 2;
    let oy = (height - linhas * px) / 2;
    return { px, ox, oy };
}

function desenharOlho() {
    let { px, ox, oy } = calcularAreaOlho();

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
                if (estaFalando) alpha = 255 - (pulsoLuz * 50);
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
                rect(ox + x * px, oy + y * px, px - 1, px - 1, 2);
            }
        }
    }
}

function verificarFormatoOlho(distCentro, dy, raioComDeformacao) {
    let formato = obterFormatoAtual();
    switch (formato) {
        case "meia_lua":         return distCentro < raioComDeformacao && dy > -raioComDeformacao * 0.3;
        case "arregalado":       return distCentro < raioComDeformacao * 1.2;
        case "levemente_arregalado": return distCentro < raioComDeformacao * 1.08;
        case "erratico":
        case "distorcido_leve":
        case "circular":
        default:                 return distCentro < raioComDeformacao;
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
            if (dif < 0.5) { resultado.ativo = true; resultado.alpha = 240; }
        }
        if (dist < 1.5) { resultado.ativo = true; resultado.alpha = 255; }

    } else {
        let distPupila = dist(x, y, centroX + posicaoPupila.x, centroY + posicaoPupila.y);
        let raioPupila = raioOlho * estado.tamanhoPupila;
        if (estaFalando) raioPupila *= (1 + pulsoLuz * 0.3);
        if (distPupila < raioPupila) { resultado.ativo = true; resultado.alpha = 255; }
        if (distPupila < raioPupila * 0.35) { resultado.ativo = true; resultado.alpha = 180; }
    }

    return resultado;
}

function windowResized() {
    resizeCanvas(windowWidth, windowHeight);
    tamanhoPixel = min(width, height) / colunas;
}