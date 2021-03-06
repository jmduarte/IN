import numpy as np
import torch
import imp
try:
    imp.find_module('setGPU')
    import setGPU
except ImportError:
    pass    
import argparse
import onnx
import warnings
from onnx_tf.backend import prepare
import os
    
N = 60 # number of charged particles
N_sv = 5 # number of SVs 
n_targets = 2 # number of classes
if os.path.isdir('/bigdata/shared/BumbleB'):
    save_path = '/bigdata/shared/BumbleB/convert_20181121_ak8_80x_deepDoubleB_db_pf_cpf_sv_dl4jets_test/'
elif os.path.isdir('/eos/user/w/woodson/IN'):
    save_path = '/eos/user/w/woodson/IN/convert_20181121_ak8_80x_deepDoubleB_db_pf_cpf_sv_dl4jets_test/'

params_2 = ['track_ptrel',     
          'track_erel',     
          'track_phirel',     
          'track_etarel',     
          'track_deltaR',
          'track_drminsv',     
          'track_drsubjet1',     
          'track_drsubjet2',
          'track_dz',     
          'track_dzsig',     
          'track_dxy',     
          'track_dxysig',     
          'track_normchi2',     
          'track_quality',     
          'track_dptdpt',     
          'track_detadeta',     
          'track_dphidphi',     
          'track_dxydxy',     
          'track_dzdz',     
          'track_dxydz',     
          'track_dphidxy',     
          'track_dlambdadz',     
          'trackBTag_EtaRel',     
          'trackBTag_PtRatio',     
          'trackBTag_PParRatio',     
          'trackBTag_Sip2dVal',     
          'trackBTag_Sip2dSig',     
          'trackBTag_Sip3dVal',     
          'trackBTag_Sip3dSig',     
          'trackBTag_JetDistVal'
         ]

params_3 = ['sv_ptrel',
          'sv_erel',
          'sv_phirel',
          'sv_etarel',
          'sv_deltaR',
          'sv_pt',
          'sv_mass',
          'sv_ntracks',
          'sv_normchi2',
          'sv_dxy',
          'sv_dxysig',
          'sv_d3d',
          'sv_d3dsig',
          'sv_costhetasvpv'
         ]

def main(args):
    test_2 = np.load(save_path + 'test_0_features_2.npy')
    test_3 = np.load(save_path + 'test_0_features_3.npy')
    test_2 = np.swapaxes(test_2, 1, 2)
    test_3 = np.swapaxes(test_3, 1, 2)
    print(test_2.shape)
    print(test_3.shape)
    test = test_2
    params = params_2
    test_sv = test_3
    params_sv = params_3
    label = 'new'
    from gnn import GraphNet
    gnn = GraphNet(N, n_targets, len(params), args.hidden, N_sv, len(params_sv),
                   vv_branch=int(args.vv_branch),
                   De=args.De,
                   Do=args.Do)
    gnn.load_state_dict(torch.load('%s/gnn_%s_best.pth'%(args.outdir,label)))
    
    batch_size = 1
    dummy_input_1 = torch.from_numpy(test[0:batch_size]).cuda()
    dummy_input_2 = torch.from_numpy(test_sv[0:batch_size]).cuda()
    #dummy_input_1 = torch.randn(32, 30, 60, device='cuda')
    #dummy_input_2 = torch.randn(32, 14, 5, device='cuda')

    out_test = gnn(dummy_input_1, dummy_input_2)

    input_names = ['input_cpf', 'input_sv']
    output_names = ['output1']

    torch.onnx.export(gnn, (dummy_input_1, dummy_input_2), "%s/gnn.onnx"%args.outdir, verbose=True,
                      input_names = input_names, output_names = output_names)

    # Load the ONNX model
    model = onnx.load("%s/gnn.onnx"%args.outdir)

    # Check that the IR is well formed
    onnx.checker.check_model(model)

    # Print a human readable representation of the graph
    print(onnx.helper.printable_graph(model.graph))

    #warnings.filterwarnings('ignore') # Ignore all the warning messages in this tutorial
    tf_rep = prepare(model) # Import the ONNX model to Tensorflow
    print(tf_rep.inputs) # Input nodes to the model
    print(tf_rep.outputs) # Output nodes from the model
    #print(tf_rep.tensor_dict) # All nodes in the model
    output = tf_rep.run((test[0:batch_size],test_sv[0:batch_size]))["output1"]

    model_filename = '%s/gnn.pb'%args.outdir
    tf_rep.export_graph(model_filename)

    import tensorflow as tf
    tf.reset_default_graph()
    from tensorflow.python.platform import gfile
    constDir = './'
    with tf.Session() as sess:
        with gfile.FastGFile(model_filename, 'rb') as f:
            graph_def = tf.GraphDef()
            graph_def.ParseFromString(f.read())
            g_in = tf.import_graph_def(graph_def)
            print([n.name for n in tf.get_default_graph().as_graph_def().node])

            x = sess.graph.get_tensor_by_name('import/input_cpf:0')
            y = sess.graph.get_tensor_by_name('import/input_sv:0')
            out = sess.graph.get_tensor_by_name('import/add_33:0')
            feed_dict = {x:test[0:batch_size], y:test_sv[0:batch_size]}

            classification = sess.run(out, feed_dict)

            # make variables constant (seems to be unnecessary)
            
            #from tensorflow.python.framework import graph_util
            #from tensorflow.python.framework import graph_io

            #pred_node_names = ['import/add_33']
            #nonconstant_graph = tfsession.graph.as_graph_def()
            #constant_graph = graph_util.convert_variables_to_constants(sess, sess.graph.as_graph_def(), pred_node_names)

            #f = 'constantgraph.pb.ascii'
            #tf.train.write_graph(constant_graph, './', f, as_text=True)
            #print('saved the graph definition in ascii format at: ', os.path.join('./', f))

            #f = 'constantgraph.pb'
            #tf.train.write_graph(constant_graph, './', f, as_text=False)
            #print('saved the graph definition in pb format at: ', os.path.join('./', f))
            

    print("pytorch\n",out_test)
    #print("tensorflow\n",output)
    print("tensorflow\n",classification)
    
    
if __name__ == "__main__":
    """ This is executed when run from the command line """
    parser = argparse.ArgumentParser()
    
    # Required positional arguments
    parser.add_argument("outdir", help="Required output directory")
    parser.add_argument("vv_branch", help="Required positional argument")
    
    # Optional arguments
    parser.add_argument("--De", type=int, action='store', dest='De', default = 5, help="De")
    parser.add_argument("--Do", type=int, action='store', dest='Do', default = 6, help="Do")
    parser.add_argument("--hidden", type=int, action='store', dest='hidden', default = 15, help="hidden")

    args = parser.parse_args()
    main(args)
