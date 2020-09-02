var gulp = require('gulp');
var sass = require('gulp-sass');
var watchify = require('watchify');
var browserify = require('browserify');
var source = require('vinyl-source-stream');
var buffer = require('vinyl-buffer');
var sourcemaps = require('gulp-sourcemaps');
var es = require('event-stream');

var config = {
  js: {
    src: [
      './js/main.js',
    ],
    outputDir: './build/',
    mapDir: './maps/',
  },
  sass: {
    src: './sass/**/*.scss',
    dest: './css',
    include: ['./js/visualizers/']
  }
}


gulp.task('sass', () =>
  gulp.src(config.sass.src)
    .pipe(sass({includePaths: config.sass.include}))
    .pipe(sass().on('error', sass.logError))
    .pipe(gulp.dest(config.sass.dest))
);

gulp.task('watch:sass', () =>
  gulp.watch([config.sass.src, './js/visualizers/*/*.scss'], gulp.series('sass'))
);


var buildJs = (watch, done) => {
    // map each js source file to a stream
    var tasks = config.js.src.map((entry) => {
      var bundler = browserify({
        entries: [entry],
        cache: {},
        packageCache: {},
        debug: true,
        transform: []
      });

      var bundle = () => bundler.bundle()
          .pipe(source(entry))
          .pipe(buffer())
          .pipe(sourcemaps.init({ loadMaps : true }))
          .pipe(sourcemaps.write(config.js.mapDir))
          .pipe(gulp.dest(config.js.outputDir));

      if (watch) {
        bundler = watchify(bundler);
        bundler.on('update', bundle);
        bundler.on('log', console.log);
      }

      return bundle();
    });

    // create a merged stream
    merged = es.merge(tasks);

    if (watch) {
      return merged;
    } else {
      return merged.on('end', done);
    }
};

gulp.task('js', (done) => buildJs(false, done));
gulp.task('watch:js', (done) => buildJs(true, done));


gulp.task('watch', gulp.parallel('watch:js', 'watch:sass'));
gulp.task('default', gulp.parallel('sass', 'js'));
