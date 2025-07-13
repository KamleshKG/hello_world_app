pipeline {
    agent any
    environment {
        FLUTTER_HOME = '/opt/flutter'
        PATH = "${FLUTTER_HOME}/bin:${PATH}"
        PUB_HOSTED_URL = 'https://trialjq29zm.jfrog.io/artifactory/api/pub/dart-pub-pub/'
        ARTIFACTORY_URL = 'https://trialjq29zm.jfrog.io/artifactory/flutter-app-releases-generic-local/'
        FLUTTER_CACHE = "${FLUTTER_HOME}/bin/cache"
    }
    stages {
        stage('Setup Flutter') {
            steps {
                sh '''
                sudo chown -R jenkins:jenkins ${FLUTTER_HOME}
                sudo chmod -R 775 ${FLUTTER_CACHE}
                flutter doctor -v
                '''
            }
        }
        stage('Checkout') {
            steps {
                git branch: 'main', 
                url: 'https://github.com/KamleshKG/hello_world_app.git'
            }
        }
        stage('Dependencies') {
            steps {
                sh 'flutter pub get'
            }
        }
        stage('Build APK') {
            steps {
                sh 'flutter build apk --release --no-pub'
            }
        }
        stage('Publish to Artifactory') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'jfrog-creds',
                    usernameVariable: 'JFROG_USER',
                    passwordVariable: 'JFROG_PASS'
                )]) {
                    sh '''
                    curl -u$JFROG_USER:$JFROG_PASS \
                         -H "X-Checksum-Sha1: $(sha1sum build/app/outputs/flutter-apk/app-release.apk | cut -d' ' -f1)" \
                         -T build/app/outputs/flutter-apk/app-release.apk \
                         "${ARTIFACTORY_URL}${BUILD_NUMBER}/app-release.apk"
                    '''
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'build/app/outputs/flutter-apk/*.apk', fingerprint: true
            sh 'flutter clean'
        }
    }
}