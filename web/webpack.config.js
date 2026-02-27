const path = require('path');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const TerserPlugin = require('terser-webpack-plugin');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');

module.exports = (env, argv) => ({
  entry: {
    index: './src/index.ts',
    annotator: './src/annotator.ts',
    senior: './src/senior.ts',
  },
  output: {
    filename: '[name].bundle.js',
    path: path.resolve(__dirname, '../static'),
    clean: true,
  },
  optimization: {
    minimize: true,
    minimizer: [
      new TerserPlugin({
        extractComments: false,
        terserOptions: { format: { comments: false } },
      }),
    ],
  },
  module: {
    rules: [
      { test: /\.ts$/, use: 'ts-loader', exclude: /node_modules/ },
      { test: /\.css$/, use: [MiniCssExtractPlugin.loader, 'css-loader'] },
    ],
  },
  resolve: { extensions: ['.ts', '.js'] },
  plugins: [
    new MiniCssExtractPlugin({ filename: 'style.css' }),
    new HtmlWebpackPlugin({
      template: './src/index.html',
      filename: 'index.html',
      chunks: ['index'],
      hash: true,
    }),
    new HtmlWebpackPlugin({
      template: './src/annotator.html',
      filename: 'annotator.html',
      chunks: ['annotator'],
      hash: true,
    }),
    new HtmlWebpackPlugin({
      template: './src/senior.html',
      filename: 'senior.html',
      chunks: ['senior'],
      hash: true,
    }),
  ],
  devServer: {
    static: '../static',
    port: 8000,
    open: true,
    proxy: [{ context: ['/api'], target: 'http://localhost:8000' }],
  },
  mode: argv.mode || 'development',
  devtool: argv.mode === 'production' ? false : 'source-map',
});
