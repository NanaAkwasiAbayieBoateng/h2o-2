import unittest, time, sys, random, math, getpass
sys.path.extend(['.','..','py'])
import h2o, h2o_cmd, h2o_hosts, h2o_import as h2i, h2o_util

DO_SCIPY_COMPARE = False

def twoDecimals(l): 
    if isinstance(l, list):
        return ["%.2f" % v for v in l] 
    else:
        return "%.2f" % l

def generate_scipy_comparison(csvPathname):
    # this is some hack code for reading the csv and doing some percentile stuff in scipy
    from numpy import loadtxt, genfromtxt, savetxt

    dataset = loadtxt(
        open(csvPathname, 'r'),
        delimiter=',');
        # dtype='int16');

    print "csv read for training, done"
    # we're going to strip just the last column for percentile work
    # used below
    NUMCLASSES = 10
    print "csv read for training, done"

    # data is last column
    # drop the output
    print dataset.shape
    if 1==1:
        n_features = len(dataset[0]) - 1;
        print "n_features:", n_features

        # get the end
        # target = [x[-1] for x in dataset]
        # get the 2nd col
        target = [x[1] for x in dataset]

        print "histogram of target"
        from scipy import histogram
        print histogram(target, bins=NUMCLASSES)

        print target[0]
        print target[1]

    from scipy import stats
    thresholds   = [0.01, 0.05, 0.1, 0.25, 0.33, 0.5, 0.66, 0.75, 0.9, 0.95, 0.99]
    per = [100 * t for t in thresholds]
    print "scipy per:", per
    a = stats.scoreatpercentile(dataset, per=per)
    print "scipy percentiles:", a

class Basic(unittest.TestCase):
    def tearDown(self):
        h2o.check_sandbox_for_errors()

    @classmethod
    def setUpClass(cls):
        global SEED, localhost
        SEED = h2o.setup_random_seed()
        localhost = h2o.decide_if_localhost()
        if (localhost):
            h2o.build_cloud(node_count=1, base_port=54327)
        else:
            h2o_hosts.build_cloud_with_hosts(node_count=1)

    @classmethod
    def tearDownClass(cls):
        h2o.tear_down_cloud()

    def test_summary2_unifiles(self):
        SYNDATASETS_DIR = h2o.make_syn_dir()
        tryList = [
            # colname, (min, 25th, 50th, 75th, max)
            ('runif.csv', 'x.hex', [
                ('' ,  1.00, 5002.00, 10002.00, 15002.00, 20000.00),
                ('D', -5000.00, -3731.95, -2445.89, -1185.58, 99.90),
                ('E', -99997.52, -49086.55, 1613.54, 50737.49, 99995.68),
                ('F', -1.00, -0.49, 0.01, 0.50, 1.00),
            ]),

            ('runifA.csv', 'A.hex', [
                ('',  1.00, 26.51, 52.00, 77.00, 100.00),
                ('x', -99.72, -39.38, 4.62, 54.96, 91.73),
            ]),

            ('runifB.csv', 'B.hex', [
                ('',  1.00, 2502.00, 5002.00, 7502.00, 10000.00),
                ('x', -100.00, -50.26, 0.85, 51.26, 99.97),
            ]),

            ('runifC.csv', 'C.hex', [
                ('',  1.00, 25002.00, 50002.00, 75002.00, 100000.00),
                ('x', -100.00, -50.45, -1.18, 49.28, 100.00),
            ]),

        ]

        timeoutSecs = 10
        trial = 1
        n = h2o.nodes[0]
        lenNodes = len(h2o.nodes)

        x = 0
        timeoutSecs = 60
        for (csvFilename, hex_key, expectedCols) in tryList:
            h2o.beta_features = False

            csvPathname = csvFilename
            parseResult = h2i.import_parse(bucket='smalldata', path=csvPathname, 
                schema='put', hex_key=hex_key, timeoutSecs=10, doSummary=False)

            print csvFilename, 'parse time:', parseResult['response']['time']
            print "Parse result['destination_key']:", parseResult['destination_key']

            # We should be able to see the parse result?
            inspect = h2o_cmd.runInspect(None, parseResult['destination_key'])
            print "\n" + csvFilename

            numRows = inspect["num_rows"]
            numCols = inspect["num_cols"]

            h2o.beta_features = True
            summaryResult = h2o_cmd.runSummary(key=hex_key)
            h2o.verboseprint("summaryResult:", h2o.dump_json(summaryResult))

            summaries = summaryResult['summaries']
            for expected, column in zip(expectedCols, summaries):
                # ('',  '1.00', '25002.00', '50002.00', '75002.00', '100000.00'),
                colname = column['colname']
                self.assertEqual(colname, expected[0])

                coltype = column['type']
                nacnt = column['nacnt']

                stats = column['stats']
                stattype= stats['type']

                # FIX! we should compare mean and sd to expected?
                mean = stats['mean']
                sd = stats['sd']

                print "colname:", colname, "mean (2 places): %s", twoDecimals(mean)
                print "colname:", colname, "std dev. (2 places): %s", twoDecimals(sd)

                zeros = stats['zeros']
                mins = stats['mins']
                h2o_util.assertApproxEqual(mins[1], expected[1], rel=0.01, msg='min is not approx. expected')

                maxs = stats['maxs']
                h2o_util.assertApproxEqual(maxs[5], expected[5], rel=0.01, msg='max is not approx. expected')

                pct = stats['pct']
                # the thresholds h2o used, should match what we expected
                expectedPct= [0.01, 0.05, 0.1, 0.25, 0.33, 0.5, 0.66, 0.75, 0.9, 0.95, 0.99]

                pctile = stats['pctile']
                h2o_util.assertApproxEqual(maxs[2], expected[2], rel=0.01, msg='25th percentile is not approx. expected')
                h2o_util.assertApproxEqual(maxs[3], expected[3], rel=0.01, msg='50th percentile (median) is not approx. expected')
                h2o_util.assertApproxEqual(maxs[4], expected[4], rel=0.01, msg='75th percentile is not approx. expected')

                hstart = column['hstart']
                hstep = column['hstep']
                hbrk = column['hbrk']
                hcnt = column['hcnt']

                print "pct:", pct
                print ""

                for b in hcnt:
                    # should we be able to check for a uniform distribution in the files?
                    e = .1 * numRows
                    # self.assertAlmostEqual(b, .1 * rowCount, delta=.01*rowCount, 
                    #     msg="Bins not right. b: %s e: %s" % (b, e))

    
                pt = twoDecimals(pctile)
                mx = twoDecimals(maxs)
                mn = twoDecimals(mins)
                print "colname:", colname, "pctile (2 places):", pt
                print "colname:", colname, "maxs: (2 places):", mx
                print "colname:", colname, "mins: (2 places):", mn

                # FIX! we should do an exec and compare using the exec quantile too
                compareActual = mn[0], pt[3], pt[5], pt[7], mx[0]
                print "min/25/50/75/max colname:", colname, "(2 places):", compareActual
                print "maxs colname:", colname, "(2 places):", mx
                print "mins colname:", colname, "(2 places):", mn

            trial += 1

            if DO_SCIPY_COMPARE:
                csvPathname1 = h2i.find_folder_and_filename('smalldata', csvPathname, returnFullPath=True)
                generate_scipy_comparison(csvPathname1)

if __name__ == '__main__':
    h2o.unit_main()
