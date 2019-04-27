from flask import Flask
from flask_restful import reqparse, abort, Api, Resource
import FileVerif
import spml2csv
import morpho_doc

app = Flask(__name__)
api = Api(app)

# verification response -- will be returned as json.
verificationResult = {
    'verificationSuccess' : False,
    'message' : ''
}

# converter response
converterResult = {
    'convertSuccess': False,
    'message' : '',
    'generatedCsv' : ''
}

# parser = reqparse.RequestParser()

class Verification(Resource):
    def get(self):
        verifOk, verifMsg = FileVerif.proceed()
        if verifOk:
            verificationResult['verificationSuccess'] = True
        else:
            verificationResult['verificationSuccess'] = False

        verificationResult['message'] = verifMsg

        return verificationResult

class ServerStat(Resource):
    def get(self):
        return { 'serverUp' : True }

class SimpmlConverter(Resource):
    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('uxp')
        self.reqparse.add_argument('csv')
        super(SimpmlConverter, self).__init__()

    def post(self):
        args = self.reqparse.parse_args()
        convertOk, convertMsg, resultCsv = spml2csv.runAsModule(args['uxp'])
        converterResult['convertSuccess'] = convertOk
        converterResult['message'] = convertMsg
        converterResult['generatedCsv'] = resultCsv
        return converterResult

class ExMorphoDocConverter(Resource):
    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('xml')
        self.reqparse.add_argument('csv')
        super(ExMorphoDocConverter, self).__init__()
    
    def post(self):
        args = self.reqparse.parse_args()
        convertOk, convertMsg, resultCsv = morpho_doc.runAsModule(args['xml'])
        converterResult['convertSuccess'] = convertOk
        converterResult['message'] = convertMsg
        converterResult['generatedCsv'] = resultCsv
        return converterResult

# setup API resource mapping
api.add_resource(Verification, '/run')
api.add_resource(ServerStat, '/getServerStatus')
api.add_resource(SimpmlConverter, '/convertUxp')
api.add_resource(ExMorphoDocConverter, '/convertExMorphoDoc')

if __name__ == '__main__':
    app.run(debug=True)
