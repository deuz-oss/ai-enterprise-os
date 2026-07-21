import 'package:flutter/material.dart';

void main() {
  runApp(const TemplateApp());
}

class TemplateApp extends StatelessWidget {
  const TemplateApp({super.key});

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(home: Scaffold(body: Center(child: Text('__NAME__'))));
  }
}

