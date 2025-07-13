pipeline {
    agent any
    environment {
        FLUTTER_HOME = '/opt/flutter'
        PATH = "${FLUTTER_HOME}/bin:${PATH}"
        PUB_HOSTED_URL = 'https://trialjq29zm.jfrog.io/artifactory/api/pub/dart-pub-pub/'
    }
    stages {
        stage('Auth Setup') {
            steps {
                withCredentials([
                    string(credentialsId: 'artifactory-token', variable: 'DART_PUB_TOKEN')
                ]) {
                    sh '''
                    # Configure Dart pub credentials
                    mkdir -p ~/.config/dart
                    cat > ~/.config/dart/pub-credentials.json <<EOF
                    {
                      "accessToken":"$DART_PUB_TOKEN",
                      "refreshToken":"$DART_PUB_TOKEN",
                      "tokenEndpoint":"$PUB_HOSTED_URL",
                      "scopes":["$PUB_HOSTED_URL"],
                      "expiration":9999999999999
                    }
                    EOF
                    '''
                }
            }
        }
        stage('Build') {
            steps {
                sh '''
                flutter pub get
                flutter build apk --release
                '''
            }
        }
    }
}