

let socket
let estadoAtual = "neutro";

function setup(){
    canvas.createCanvas(windowWidth, windowHeight);

    socket = io();

    socket.on('mudar_estado', function(dados) {
        estadoAtual = dados.emocao
        console.log("Estado recebido: ", estadoAtual)
    })
}

function draw(){
    background(0);
    translate(width / 2, height / 2);

    noStroke()

    if(estadoAtual === "falando"){
        fill(255, 0, 0)
    }
    else if (estadoAtual === "neutro"){
        fill(0, 255, 0)
    }

    ellipse(0,0, 200, 200)
}

function windowResized() {
    resizeCanvas(windowWidth, windowHeight);
}