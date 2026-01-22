const emocaoAtual = "neutro"
const estaFalando = false
let cols = 32
let rows = 32
let cellH
let cellW
let grid = []

EMOCOES = {

}


function jsAtualizarRosto(emocao, estafalando){
    console.log("jsAtualizarRosto")
}

function jsAtualizarTexto(texto){
    console.log("jsAtualizarTexto")
}

function setup(){
    createCanvas(windowWidth, windowHeight) // 500, 400
    frameRate(60)
    cellW = width / cols; 
    cellH = height / rows; 
    for (let x = 0; x < rows; x++) {
        grid[x] = [];
        for (let y = 0; y < cols; y++) {
            grid[x][y] = 0;
        }
    }
}

function draw(){
    background(0)
    for (let x = 0; x < rows; x++) {
        for (let y = 0; y < cols; y++) {

            if (grid[x][y] === 1) {
                fill(255);
            } else {
                fill(30);
            }
            
            let valorNoise = noise(
                y * cellH,
                x * cellW,
                frameCount * 60
            )

            if (valorNoise > 0.5){
                grid[x][y] = 1
            }

            rect(
                x * cellW, //16000
                y * cellH, //12.800
                cellW,
                cellH
            );
        }
    }
}