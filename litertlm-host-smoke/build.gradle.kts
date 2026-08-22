plugins {
    id("org.jetbrains.kotlin.jvm")
    application
}

kotlin {
    jvmToolchain(17)
}

dependencies {
    implementation("com.google.ai.edge.litertlm:litertlm-jvm:0.16.1")
    implementation("com.google.code.gson:gson:2.13.2")
    testImplementation(kotlin("test"))
}

application {
    mainClass.set("dev.localflow.litertlmhost.S1MiniLiteRtHostSmokeKt")
}

tasks.test {
    useJUnitPlatform()
}
